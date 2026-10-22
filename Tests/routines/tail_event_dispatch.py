#!/usr/bin/env python3
"""Execute the compiled tail-event helpers on Yaze's CPU.

TailEvent_Load/Store must send areas $A0-$BF to TailEventFlags ($7EF4C0+i)
and every other index to the legacy $7EF280,X byte, in any M/X width, with
caller X/Y/DB/D/SP/C and widths preserved. TailEvent_MigrateSave must clear
the 32 flags once and stamp the version, and leave a stamped save untouched.
A temporary ROM copy and private WRAM fixtures; routine/ABI evidence only,
not save/load, PPU or route proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

WRAM = 0x7E0000
SP = 0x1FFF
LEGACY = 0x7EF280
FLAGS = 0x7EF4C0
VERSION = 0x7EF4E0
CURRENT = 0xA1
TRAMPOLINE = 0x18000  # runner sentinel at $7F8000


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def symbol(text, name):
    matches = re.findall(r'^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?'
                         + re.escape(name) + r'$', text, re.M)
    require(len(matches) == 1, f'Expected one symbol {name}')
    bank, address = matches[0]
    return int(bank, 16) << 16 | int(address, 16)


def base_ram():
    ram = bytearray((n * 37 + 11) & 255 for n in range(0x20000))
    return ram


def scratch_masked(after, reference):
    """Copy runner-owned bytes (stack window, $7F8000 trampoline) from after."""
    out = bytearray(reference)
    for lo, hi in ((SP - 0x40, SP + 1), (TRAMPOLINE, TRAMPOLINE + 0x10)):
        out[lo:hi] = after[lo:hi]
    return bytes(out)


def target(index):
    return FLAGS + index - 0xA0 if 0xA0 <= index < 0xC0 else LEGACY + index


def dispatch_cases():
    # (index, m8, x8, carry)
    out = []
    for index in (0x00, 0x1B, 0x80, 0x99, 0x9F, 0xA0, 0xA5, 0xBF, 0xC0, 0xFF):
        for m8, x8 in ((1, 1), (1, 0), (0, 0)):
            for carry in (0, 1):
                out.append((index, m8, x8, carry))
    out += [(0x1A0, 1, 0, 1), (0x1BF, 0, 0, 0)]  # 16-bit X past the tail window stays legacy
    return out


def dispatch_request(entry, kind, case):
    index, m8, x8, carry = case
    ram = base_ram()
    p = (0x20 if m8 else 0) | (0x10 if x8 else 0) | carry
    a = 0x5AC3
    request = dict(entry=entry, reset_ram=True,
                   registers=dict(a=a, x=index, y=0x1234 if not x8 else 0x34, p=p, db=0x7E, d=0, sp=SP),
                   writes=[dict(address=WRAM, bytes=list(ram))],
                   reads=[dict(address=WRAM, length=len(ram))],
                   trace_writes=True, max_steps=200)
    return ram, request


def verify_dispatch(kind, case, before, result):
    index, m8, x8, carry = case
    name = f'{kind} X={index:03X} m8={m8} x8={x8} c={carry}'
    require(result.get('returned'), f'{name}: CPU did not return: {result.get("error")}')
    require(not result.get('stub_calls') and not result.get('mmio_writes'), f'{name}: device path')
    regs = result['registers']
    p_in = (0x20 if m8 else 0) | (0x10 if x8 else 0) | carry
    for key, value in dict(x=index, db=0x7E, d=0, sp=SP, e=0).items():
        require(regs[key] == value, f'{name}: {key}={regs[key]:X}, expected {value:X}')
    require(regs['y'] == (0x1234 if not x8 else 0x34), f'{name}: Y changed')
    after = bytes(result['reads'][0]['bytes'])
    address = target(index)
    width = 1 if m8 else 2
    if kind == 'load':
        value = int.from_bytes(before[address - WRAM:address - WRAM + width], 'little')
        a = (0x5A00 | value) if m8 else value
        require(regs['a'] == a, f'{name}: A={regs["a"]:04X}, expected {a:04X}')
        nz = (0x02 if value == 0 else 0) | (0x80 if value >> (8 * width - 1) else 0)
        require(regs['p'] == (p_in & ~0x82) | nz, f'{name}: P={regs["p"]:02X}')
        require(after == scratch_masked(after, before), f'{name}: load changed RAM')
    else:
        require(regs['a'] == 0x5AC3 and regs['p'] == p_in, f'{name}: A/P changed')
        expected = bytearray(before)
        expected[address - WRAM:address - WRAM + width] = (0x5AC3).to_bytes(2, 'little')[:width]
        require(after == scratch_masked(after, expected), f'{name}: store wrote outside {address:06X}')
    return dict(name=name, address=f'{address:06X}', steps=result['steps'])


def migrate_request(entry, version):
    ram = base_ram()
    ram[VERSION - WRAM] = version
    request = dict(entry=entry, reset_ram=True,
                   registers=dict(a=0x1111, x=0x55, y=0x66, p=0x30, db=0x7E, d=0, sp=SP),
                   writes=[dict(address=WRAM, bytes=list(ram))],
                   reads=[dict(address=WRAM, length=len(ram))],
                   trace_writes=True, max_steps=1000)
    return ram, request


def verify_migrate(version, before, result):
    name = f'migrate version={version:02X}'
    require(result.get('returned'), f'{name}: CPU did not return: {result.get("error")}')
    regs = result['registers']
    for key, value in dict(x=0x55, y=0x66, db=0x7E, d=0, sp=SP, e=0).items():
        require(regs[key] == value, f'{name}: {key}={regs[key]:X}, expected {value:X}')
    require(regs['p'] & 0x30 == 0x30, f'{name}: M/X width changed')
    after = bytes(result['reads'][0]['bytes'])
    expected = bytearray(before)
    if version != CURRENT:
        expected[FLAGS - WRAM:FLAGS - WRAM + 32] = bytes(32)
        expected[VERSION - WRAM] = CURRENT
    require(after == scratch_masked(after, expected), f'{name}: unexpected RAM result')
    return dict(name=name, cleared=version != CURRENT, steps=result['steps'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('rom', 'symbols', 'cpu-runner'):
        parser.add_argument('--' + arg, type=Path, required=True)
    args = parser.parse_args()
    rom, text = args.rom.read_bytes(), args.symbols.read_text()
    require(0 < len(rom) <= 0x400000, 'Expected headerless LoROM <=4MiB')
    padding = (-len(rom)) % 0x8000
    require(symbol(text, 'TailEventFlags') == FLAGS and symbol(text, 'TailEventVersion') == VERSION,
            'Tail event storage moved')
    entries = {kind: symbol(text, name) for kind, name in (
        ('load', 'TailEvent_Load'), ('store', 'TailEvent_Store'), ('migrate', 'TailEvent_MigrateSave'))}
    plans = []
    for kind in ('load', 'store'):
        for case in dispatch_cases():
            before, request = dispatch_request(entries[kind], kind, case)
            plans.append((lambda r, k=kind, c=case, b=before: verify_dispatch(k, c, b, r), request))
    for version in (0x00, 0xFF, 0xA5, CURRENT):
        before, request = migrate_request(entries['migrate'], version)
        plans.append((lambda r, v=version, b=before: verify_migrate(v, b, r), request))
    with tempfile.TemporaryDirectory(prefix='tail-event-dispatch-') as folder:
        copy = Path(folder) / 'routine-fixture.sfc'
        copy.write_bytes(rom + bytes([0xFF]) * padding)
        run = subprocess.run([str(args.cpu_runner.resolve()), str(copy)],
                             input=''.join(json.dumps(p[1]) + '\n' for p in plans),
                             text=True, capture_output=True, timeout=60, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), f'Expected {len(plans)} CPU responses, got {len(lines)}')
    results = [check(json.loads(line)) for (check, _), line in zip(plans, lines)]
    require(args.rom.read_bytes() == rom and args.symbols.read_text() == text,
            'Input ROM/symbols changed during routine check')
    print(json.dumps(dict(passed=True, case_count=len(results),
                          tail_cases=sum(1 for r in results
                                         if FLAGS <= int(r.get('address', '0'), 16) < FLAGS + 32),
                          rom_sha256=hashlib.sha256(rom).hexdigest(),
                          entries={k: f'{v:06X}' for k, v in entries.items()},
                          claim='compiled helpers on Yaze CPU; private RAM fixtures; no save/load or route acceptance'),
                     indent=2))


if __name__ == '__main__':
    main()
