#!/usr/bin/env python3
"""Check compiled D3 gate position stop with synthetic WRAM and no stubs.

This checks geometry, fast crossing, scope and preservation. Native zap damage,
Cape activation and rendered traversal still require the parent's emulator run.
"""
import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path
import subprocess
import tempfile

from d3_prison_state import FLAGS, SAVE, SP, SWORD, WRAM, digest, physical, require, symbol

HELPER = 'D3Prison_BossGateStopCrossing'
DISPATCH = 'D3Prison_BossGateDispatch'


@dataclass(frozen=True)
class Case:
    name: str
    stopped: bool = True
    x: int = 0x1378
    y: int = 0x076B
    delta: int = 0xFF
    flags: int = 0x29
    sword: int = 2
    cloak: int = 0
    immunity: int = 0
    room: int = 0x39
    dungeon: int = 0x10
    indoors: int = 1
    module: int = 7
    submodule: int = 0
    actor: int = 0x40
    state: int = 9
    freeze: int = 0
    floor: int = 0
    offscreen: int = 0
    properties: int = 0
    p: int = 0xF5


def cases():
    base = Case('ordinary-native-recoil-retained')
    rows = [base,
            replace(base, name='stone-north-contact', cloak=1, immunity=1),
            replace(base, name='post-damage-invulnerability', immunity=1),
            replace(base, name='stationary-inside-band', y=0x075C, delta=0),
            replace(base, name='north-edge-contact', y=0x0754),
            replace(base, name='fast-north-crosses-whole-band', y=0x0744, delta=0xCB),
            replace(base, name='fast-minus32-crosses-whole-band', y=0x0753, delta=0xE0),
            replace(base, name='left-edge-contact', x=0x1358),
            replace(base, name='right-edge-contact', x=0x1397),
            replace(base, name='smith-sentinel-does-not-open', flags=0x2B, sword=0xFF),
            replace(base, name='active-offcamera-property', offscreen=1, properties=0x80)]
    for name, changes in (
        ('safe-south-row', dict(y=0x076C)),
        ('already-north-slow', dict(y=0x0753)),
        ('already-north-fast', dict(y=0x0700, delta=0xC0)),
        ('southward-retreat', dict(y=0x075C, delta=2)),
        ('outside-left', dict(x=0x1357)),
        ('outside-right', dict(x=0x1398)),
        ('escaped-valid-blade', dict(flags=0x2B)),
        ('other-room', dict(room=0x38)),
        ('full-room-alias', dict(room=0x139)),
        ('other-dungeon', dict(dungeon=0xFF)),
        ('outdoors', dict(indoors=0)),
        ('menu', dict(module=0x0E)),
        ('room-transition', dict(submodule=2)),
        ('other-sprite', dict(actor=0x93)),
        ('actor-prep', dict(state=8)),
        ('freeze', dict(freeze=1)),
        ('different-floor', dict(floor=1)),
        ('inactive-offcamera', dict(offscreen=1)),
    ):
        rows.append(replace(base, name=name, stopped=False, **changes))
    for p in (0x04, 0x14, 0x24):
        rows.append(replace(base, name=f'stone-width-{p:02X}', cloak=1, immunity=1, p=p))
    return rows


def fixture(case, entry):
    low = bytearray((n * 37 + 11) & 255 for n in range(0x2000))
    save = bytearray((n * 53 + 17) & 255 for n in range(0x100))
    slot = 7
    values = {
        0x10: case.module, 0x11: case.submodule, 0x1B: case.indoors,
        0x40C: case.dungeon, 0x30: case.delta, 0x55: case.cloak,
        0x37B: case.immunity, 0xFC1: case.freeze, 0xEE: case.floor,
        0x27: 0x30, 0x28: 0, 0x46: 0x0C, 0x4D: 1, 0x360: 0x40, 0x373: 2,
        0xE20+slot: case.actor, 0xDD0+slot: case.state, 0xF20+slot: 0,
        0xF00+slot: case.offscreen, 0xCAA+slot: case.properties,
        0xD10+slot: 0x78, 0xD30+slot: 0x13,
        0xD00+slot: 0x5C, 0xD20+slot: 0x07,
    }
    for offset, value in values.items():
        low[offset] = value
    for offset, value in ((0x20, case.y), (0x22, case.x), (0xA0, case.room)):
        low[offset:offset+2] = value.to_bytes(2, 'little')
    save[FLAGS-SAVE], save[SWORD-SAVE] = case.flags, case.sword
    registers = dict(a=0xBE9A, x=slot, y=0x5A if case.p & 0x10 else 0xA65A,
                     p=case.p, db=5, d=0, sp=SP)
    request = dict(entry=entry, reset_ram=True, registers=registers,
                   writes=[dict(address=WRAM, bytes=list(low)),
                           dict(address=SAVE, bytes=list(save))],
                   reads=[dict(address=WRAM, length=len(low)),
                          dict(address=SAVE, length=len(save))],
                   trace_writes=True, max_steps=250)
    return low, save, request


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
    rom, symbols = inputs[args.rom], inputs[args.symbols].decode()
    require(0 < len(rom) <= 0x400000 and len(rom) % 0x8000 != 0x200,
            'Expected headerless LoROM <=4 MiB')
    helper, dispatch = symbol(symbols, HELPER), symbol(symbols, DISPATCH)
    offset = lambda pc: (pc >> 16) * 0x8000 + (pc & 0x7FFF)
    require(rom[offset(0x05D543):offset(0x05D543)+4] ==
            b'\x22' + dispatch.to_bytes(3, 'little'), 'Native gate dispatch is not hooked')
    sequence = b'\x22\x63\xF0\x1D\x22' + helper.to_bytes(3, 'little') + b'\x6B'
    require(sequence in rom[offset(dispatch):offset(helper)],
            'Closed gate must run native zap before the tested position stop')
    plans = [(case, *fixture(case, helper)) for case in cases()]
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix='d3-boss-contact-') as folder:
        copy = Path(folder) / 'candidate.sfc'
        copy.write_bytes(rom + b'\xFF' * padding)
        run = subprocess.run([str(args.cpu_runner), str(copy)],
                             input=''.join(json.dumps(p[3])+'\n' for p in plans),
                             capture_output=True, text=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), 'Wrong number of CPU results')
    results = []
    for (case, before, save, request), line in zip(plans, lines):
        result = json.loads(line)
        require(result.get('returned'), f'{case.name}: {result.get("error")}')
        require(not result.get('stub_calls') and not result.get('mmio_writes'),
                f'{case.name}: unexpected stub/device access')
        regs = result['registers']
        for key in ('a', 'x', 'y', 'db', 'd', 'sp', 'p'):
            require(regs[key] == request['registers'][key], f'{case.name}: ABI {key}')
        require(regs['e'] == 0, f'{case.name}: left native mode')
        require(len(result['reads']) == 2, f'{case.name}: wrong read block count')
        after, after_save = (bytes(row['bytes']) for row in result['reads'])
        require(len(after) == len(before), f'{case.name}: truncated WRAM output')
        require(after_save == save, f'{case.name}: changed inventory/SRAM')
        expected = bytearray(before)
        if case.stopped:
            expected[0x20:0x22] = (0x076C).to_bytes(2, 'little')
        stack = set(range(WRAM+SP-0x30, WRAM+SP+1))
        for index, (actual, wanted) in enumerate(zip(after, expected)):
            require(WRAM+index in stack or actual == wanted,
                    f'{case.name}: WRAM ${index:04X} changed incorrectly')
        allowed = stack | set(range(0x7F8000, 0x7F8004)) | set(range(WRAM, WRAM+6))
        if case.stopped:
            allowed.update((WRAM+0x20, WRAM+0x21))
        writes = {physical(row['address']) for row in result.get('writes', [])}
        require(writes <= allowed, f'{case.name}: undeclared writes {writes-allowed}')
        if case.stopped:
            require({WRAM+0x20, WRAM+0x21} <= writes, f'{case.name}: Y stop not written')
        results.append(dict(name=case.name, passed=True, stopped=case.stopped,
                            steps=result['steps'], before_y=case.y,
                            after_y=int.from_bytes(after[0x20:0x22], 'little')))
    require(all(p.read_bytes() == b for p,b in inputs.items()), 'Input changed during check')
    output = dict(passed=True, case_count=len(results), cases=results,
                  input_sha256={str(p): digest(b) for p,b in inputs.items()},
                  script_sha256=digest(Path(__file__).read_bytes()),
                  runner_copy_padding_bytes=padding, stubs=[], claim=__doc__)
    text = json.dumps(output, indent=2)+'\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
