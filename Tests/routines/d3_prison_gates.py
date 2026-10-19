#!/usr/bin/env python3
"""Check compiled D3 wing/boss predicates with synthetic WRAM, without stubs.

This proves the gate decisions and register/memory contracts, not native door
appearance, room traversal, boss contact, or gameplay acceptance.
"""
import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path
import subprocess
import tempfile

from d3_prison_state import FLAGS, SAVE, SP, SWORD, WRAM, digest, physical, require, symbol

OPEN = 'D3Prison_WingIsOpen'
ENTRY = 'D3Prison_WingEntranceAllowed'
WARP = 'D3Prison_WingWarpAllowed'
BOSS = 'D3Prison_BossGateIsOpen'


@dataclass(frozen=True)
class Case:
    name: str
    helper: str
    carry: int
    flags: int = 0x29
    sword: int = 2
    room: int = 0x80
    target: int = 0x55
    indoors: int = 1
    dungeon: int = 0x10
    a: int = 0xBE32
    p: int = 0xE5  # Native entrance ABI M8/X16, C initially set.
    db: int = 0x34


def cases():
    entry = Case('outside32-closed', ENTRY, 0, indoors=0)
    warp = Case('basement80-to55-closed', WARP, 0, p=0xF5, db=7)
    boss = Case('boss-before-escape-closed', BOSS, 0, p=0xF5, db=5)
    rows = [entry, warp, boss,
            replace(warp, name='prison55-to80-closed', room=0x55, target=0x80)]
    for flags in (0, 4, 0x21):
        rows.append(replace(entry, name=f'outside32-phase-{flags:02X}', flags=flags))
    for name, change in (
        ('outside32-open-smith-sentinel', dict(flags=0xAB, sword=0xFF)),
        ('mad-batter11-unchanged', dict(a=0xBE11)),
        ('hall28-unchanged', dict(a=0xBE28)),
        ('indoor32-unchanged', dict(indoors=1)),
    ):
        rows.append(replace(entry, name=name, carry=1, **change))
    for name, change in (
        ('basement80-open-smith-sentinel', dict(flags=0xAB, sword=0xFF)),
        ('prison55-open', dict(flags=2, room=0x55, target=0x80)),
        ('warp-room-high-byte-alias', dict(room=0x180)),
        ('warp-other-source', dict(room=0x81)),
        ('warp-other-destination', dict(target=0x70)),
        ('prison55-other-destination', dict(room=0x55, target=0x54)),
        ('warp-mad-batter-dungeon', dict(dungeon=0xFF)),
        ('warp-outdoors', dict(indoors=0)),
    ):
        rows.append(replace(warp, name=name, carry=1, **change))
    for sword in (0, 1, 2, 3, 4, 5, 0xFF):
        rows.append(replace(boss, name=f'boss-escaped-sword-{sword:02X}',
                            flags=0xAB, sword=sword, carry=int(2 <= sword <= 4)))
    # Permanent wing state must not depend on inventory, and both carry
    # outcomes must restore every M/X combination and hidden accumulator B.
    for p in (0x04, 0x14, 0x24, 0x34):
        for flag in (0x80, 0x82):
            rows.append(Case(f'wing-width-p{p:02X}-flag{flag:02X}', OPEN,
                             int(bool(flag & 2)), flags=flag, sword=0xFF,
                             p=p, db=0x7E))
    return rows


def fixture(case, entry):
    low = bytearray((n * 37 + 11) & 255 for n in range(0x2000))
    save = bytearray((n * 53 + 17) & 255 for n in range(0x100))
    targets = bytearray((n * 19 + 59) & 255 for n in range(0x10))
    low[0x1B], low[0x40C] = case.indoors, case.dungeon
    low[0xA0:0xA2] = case.room.to_bytes(2, 'little')
    save[FLAGS-SAVE], save[SWORD-SAVE] = case.flags, case.sword
    targets[0] = case.target
    registers = dict(a=case.a, x=7 if case.p & 0x10 else 0xA517,
                     y=0x5A if case.p & 0x10 else 0xA65A,
                     p=case.p, db=case.db, d=0, sp=SP)
    blocks = [(WRAM, low), (SAVE, save), (0x7EC000, targets)]
    request = dict(entry=entry, reset_ram=True, registers=registers,
                   writes=[dict(address=a, bytes=list(b)) for a, b in blocks],
                   reads=[dict(address=a, length=len(b)) for a, b in blocks],
                   trace_writes=True, max_steps=200)
    return blocks, request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--symbols', type=Path, required=True)
    parser.add_argument('--cpu-runner', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    inputs = {p: p.read_bytes() for p in (args.rom, args.symbols, args.cpu_runner)}
    if args.output:
        require(args.output.resolve() not in {p.resolve() for p in inputs},
                'Output must not overwrite an input')
    rom = inputs[args.rom]
    require(0 < len(rom) <= 0x400000 and len(rom) % 0x8000 != 0x200,
            'Expected headerless LoROM <=4 MiB')
    entries = {n: symbol(inputs[args.symbols].decode(), n)
               for n in (OPEN, ENTRY, WARP, BOSS, 'D3Prison_WingWarpGate')}
    offset = 7 * 0x8000 + (0xD133 & 0x7FFF)
    require(rom[offset:offset+4] == b'\x5C' +
            entries['D3Prison_WingWarpGate'].to_bytes(3, 'little'),
            'Native warp seam does not dispatch to the candidate gate')
    plans = [(c, *fixture(c, entries[c.helper])) for c in cases()]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix='d3-prison-gates-') as folder:
        copy = Path(folder) / 'candidate.sfc'
        copy.write_bytes(rom + b'\xFF' * padding)
        run = subprocess.run([str(args.cpu_runner), str(copy)],
                             input=''.join(json.dumps(p[2])+'\n' for p in plans),
                             capture_output=True, text=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), 'Wrong number of CPU runner results')
    allowed = set(range(WRAM+SP-0x20, WRAM+SP+1)) | set(range(0x7F8000, 0x7F8004))
    results = []
    for (case, blocks, request), line in zip(plans, lines):
        result = json.loads(line)
        require(result.get('returned'), f'{case.name}: {result.get("error")}')
        require(not result.get('stub_calls') and not result.get('mmio_writes'),
                f'{case.name}: unexpected stub/device access')
        regs = result['registers']
        for key in ('a', 'x', 'y', 'db', 'd', 'sp'):
            require(regs[key] == request['registers'][key], f'{case.name}: ABI {key}')
        require(regs['p'] == (case.p & 0xFE) | case.carry and regs['e'] == 0,
                f'{case.name}: status or returned Carry mismatch')
        for (address, before), after in zip(blocks, result['reads']):
            for i, (old, new) in enumerate(zip(before, after['bytes'])):
                require(address+i in allowed or old == new,
                        f'{case.name}: data changed at ${address+i:06X}')
        writes = {physical(w['address']) for w in result.get('writes', [])}
        require(writes <= allowed, f'{case.name}: undeclared writes {writes-allowed}')
        results.append(dict(name=case.name, helper=case.helper, passed=True,
                            carry=case.carry, steps=result['steps']))
    require(all(p.read_bytes() == b for p, b in inputs.items()), 'Input changed during check')
    output = dict(passed=True, case_count=len(results), cases=results,
                  input_sha256={str(p): digest(b) for p,b in inputs.items()},
                  script_sha256=digest(Path(__file__).read_bytes()),
                  runner_copy_padding_bytes=padding, stubs=[],
                  claim=__doc__)
    text = json.dumps(output, indent=2)+'\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
