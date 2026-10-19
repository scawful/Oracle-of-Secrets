#!/usr/bin/env python3
"""Execute the compiled Portal Rod helper and real allocator on Yaze's CPU.

No instruction/callee stubs, source assembly, or game/save writes. A temporary
ROM copy and private WRAM fixtures exercise the actual candidate bytes. This is
routine/ABI evidence, not natural placement, room-transition, PPU or route proof.
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
# Native allocator/LoadProperties/ResetProperties destination tables. Only the
# allocated slot may be written; load-index $0BC0 uses doubled slots outdoors.
TABLES = (
    0x0B58, 0x0B6B, 0x0B89, 0x0BA0, 0x0BB0, 0x0BE0, 0x0C9A, 0x0CAA, 0x0CBA,
    0x0CD2, 0x0CE2, 0x0D00, 0x0D10, 0x0D20, 0x0D30, 0x0D40, 0x0D50,
    0x0D60, 0x0D70, 0x0D80, 0x0D90, 0x0DA0, 0x0DB0, 0x0DC0, 0x0DD0,
    0x0DE0, 0x0DF0, 0x0E00, 0x0E10, 0x0E20, 0x0E30, 0x0E40, 0x0E50,
    0x0E60, 0x0E70, 0x0E80, 0x0E90, 0x0EA0, 0x0EB0, 0x0EC0, 0x0ED0,
    0x0EF0, 0x0F00, 0x0F10, 0x0F20, 0x0F30, 0x0F40, 0x0F50, 0x0F60,
    0x0F70, 0x0F80, 0x0F90,
)
LONG_TABLES = (0x7FF9C2, 0x7FFA1C, 0x7FFA2C, 0x7FFA3C, 0x7FFA4C)


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def symbol(text, name):
    matches = re.findall(r'^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?'
                         + re.escape(name) + r'\s*$', text, re.M)
    addresses = {int(bank + offset, 16) for bank, offset in matches}
    require(len(addresses) == 1, f'Missing/ambiguous symbol: {name}')
    return addresses.pop()


def raw(rom, address, size):
    offset = ((address >> 16) & 127) * 0x8000 + (address & 0x7FFF)
    return rom[offset:offset + size]


def physical(address):
    bank, offset = address >> 16, address & 0xFFFF
    if bank in (0x7E, 0x7F):
        return address
    require((bank & 0x7F) < 0x40 and offset < 0x2000,
            f'Unexpected non-WRAM write: {address:06X}')
    return WRAM + offset


def cases():
    # Each expected color is a behavior contract, not a Python copy of the scan.
    base_cases = [
        ('empty-stale-one', 1, [], 1, 0, 1),
        ('empty-default-zero', 0, [], 1, 2, 1),
        ('pending-only', 1, [(4, 9, 3, 0)], 1, 4, 1),
        ('invalid-survivors', 1, [(0, 0, 3, 1), (1, 8, 3, 2),
          (2, 9, 4, 2), (3, 9, 3, 0), (4, 9, 3, 3)], 1, 6, 1),
        ('accepted-blue-slot0', 1, [(0, 9, 3, 2)], 0, 0, 1),
        ('accepted-orange-slot15', 0, [(15, 9, 3, 1)], 1, 2, 1),
        ('pair-next-orange', 1, [(0, 9, 3, 2), (15, 9, 3, 1)], 0, 4, 1),
        ('pair-next-blue', 0, [(0, 9, 3, 2), (15, 9, 3, 1)], 1, 6, 1),
        ('outdoor-empty', 1, [], 1, 6, 0),
        ('full-failure-zero', 0, [(s, 9, 4, 0) for s in range(16)], 0, 0, 1),
        ('full-failure-one', 1, [(s, 9, 4, 0) for s in range(16)], 1, 0, 1),
    ]
    # Opposite source-slot floors expose native sprite-parent inheritance.
    return [case + (0, 1) for case in base_cases] + [
        ('upper-floor-cast', 1, [], 1, 0, 1, 1, 0),
        ('upper-floor-existing-pair', 1, [(0, 9, 3, 2)], 0, 2, 1, 1, 0),
    ]


def fixture(case, entry):
    name, selector, sprites, expected, direction, indoors, floor, donor_floor = case
    ram = bytearray((n * 37 + 11) & 255 for n in range(0x20000))
    ram[0x0DD0:0x0DE0] = bytes(16)
    # Deliberately stale handles/count and dormant slots' nonzero subtypes.
    ram[0x0632:0x0634] = bytes((0xFF, 0x10))
    ram[0x06FE], ram[0x0FA6] = 2, selector
    ram[0x1B], ram[0x2F] = indoors, direction
    ram[0xEE], ram[0xF20 + 5] = floor, donor_floor  # Caller X=5 below.
    ram[0x20:0x24] = bytes.fromhex('08230812')  # Link Y=$2308, X=$1208.
    ram[0x0E30:0x0E40] = bytes([2] * 16)
    for slot, state, kind, subtype in sprites:
        for table, value in ((0xDD0, state), (0xE20, kind), (0xE30, subtype)):
            ram[table + slot] = value
    free = [s for s in range(16) if ram[0xDD0 + s] == 0]
    slot = max(free) if free else None
    request = dict(entry=entry, reset_ram=True,
                   registers=dict(a=0xBE73, x=5, y=3, p=0x30, db=7, d=0, sp=SP),
                   writes=[dict(address=WRAM, bytes=list(ram))],
                   reads=[dict(address=WRAM, length=len(ram))],
                   trace_writes=True, max_steps=10000)
    return ram, slot, request


def verify(case, before, slot, result, timer):
    name, selector, sprites, expected, direction, indoors, floor, donor_floor = case
    require(result.get('returned'), f'{name}: CPU did not return: {result.get("error")}')
    require(not result.get('stub_calls') and not result.get('mmio_writes'),
            f'{name}: unexpected simulated engine/device path')
    regs = result['registers']
    for key, value in dict(x=5, y=slot if slot is not None else 255,
                           db=7, d=0, sp=SP, e=0).items():
        require(regs[key] == value, f'{name}: ABI {key}={regs[key]}, expected {value}')
    require(regs['p'] & 0x30 == 0x30, f'{name}: M/X width changed')
    after = bytes(result['reads'][0]['bytes'])
    allowed = set(range(WRAM + SP - 0x40, WRAM + SP + 1))
    # The runner's real JSL trampoline is its only host-written RAM exception.
    allowed.update(range(0x7F8000, 0x7F8004))
    if slot is not None:
        allowed.update(WRAM + t + slot for t in TABLES)
        allowed.update(t + slot for t in LONG_TABLES)
        allowed.update(WRAM + a for a in (*range(9), 0x2E, 0x3D, 0x300, 0x301, 0xFA6))
        index = slot if indoors else slot * 2
        allowed.add(WRAM + 0xBC0 + index)
        if not indoors:
            allowed.add(WRAM + 0xBC1 + index)
        require(after[0xDD0 + slot] == 9 and after[0xE20 + slot] == 3
                and after[0xE30 + slot] == 0, f'{name}: pending allocation identity wrong')
        require(after[0xF20 + slot] == floor,
                f'{name}: portal floor {after[0xF20 + slot]}, expected Link floor {floor}')
        dx, dy = {0: (0, -20), 2: (0, 31), 4: (-20, 0), 6: (20, 0)}[direction]
        x = after[0xD10 + slot] | after[0xD30 + slot] << 8
        y = after[0xD00 + slot] | after[0xD20 + slot] << 8
        require((x, y) == (0x1208 + dx, 0x2308 + dy), f'{name}: spawn coordinates wrong')
        require(after[0xBA0 + slot] == 255 and after[0xCAA + slot] & 0x80,
                f'{name}: portal protection/off-camera setup missing')
        require(after[0xD60 + slot] == after[0xD70 + slot] == 0,
                f'{name}: fractional position was not cleared')
        require((after[0x3D], after[0x2E], after[0x300], after[0x301]) == (timer, 0, 0, 1),
                f'{name}: item-animation completion changed')
    require(after[0xFA6] == expected, f'{name}: selector {after[0xFA6]}, expected {expected}')
    for offset, (a, b) in enumerate(zip(before, after)):
        require(a == b or WRAM + offset in allowed,
                f'{name}: unexpected RAM change {WRAM + offset:06X}: {a:02X}->{b:02X}')
    for write in result.get('writes', []):
        address = physical(write['address'])
        require(address in allowed, f'{name}: unexpected write {address:06X}')
    # These define one allocation; no other slot may become active or disappear.
    states = bytearray(before[0xDD0:0xDE0])
    if slot is not None:
        states[slot] = 9
    require(after[0xDD0:0xDE0] == states, f'{name}: sprite occupancy changed elsewhere')
    return dict(name=name, passed=True, allocated_slot=slot, selector=after[0xFA6],
                steps=result['steps'], registers=regs, write_count=len(result.get('writes', [])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('rom', 'symbols', 'cpu-runner'):
        parser.add_argument('--' + arg, type=Path, required=True)
    args = parser.parse_args()
    rom, text = args.rom.read_bytes(), args.symbols.read_text()
    require(0 < len(rom) <= 0x400000, 'Expected headerless LoROM <=4MiB')
    padding = (-len(rom)) % 0x8000
    entry = symbol(text, 'LinkItem_FirePortal')
    timer = raw(rom, symbol(text, 'RodAnimationTimer'), 1)[0]
    require(raw(rom, entry, 9) == bytes.fromhex('A903225DF61D10016B'),
            'Unexpected helper allocator/failure-return contract')
    require(raw(rom, 0x1DF6C5, 10) == bytes.fromhex('A90099BA0C99300E986B'),
            'Allocator no longer clears pending subtype before returning')
    plans = [(case, *fixture(case, entry)) for case in cases()]
    with tempfile.TemporaryDirectory(prefix='portal-first-cast-') as folder:
        copy = Path(folder) / 'routine-fixture.sfc'
        copy.write_bytes(rom + bytes([0xFF]) * padding)
        run = subprocess.run([str(args.cpu_runner.resolve()), str(copy)],
                             input=''.join(json.dumps(p[3]) + '\n' for p in plans),
                             text=True, capture_output=True, timeout=30, check=True)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), f'Expected {len(plans)} CPU responses, got {len(lines)}')
    results = [verify(case, before, slot, json.loads(line), timer)
               for (case, before, slot, request), line in zip(plans, lines)]
    require(args.rom.read_bytes() == rom and args.symbols.read_text() == text,
            'Input ROM/symbols changed during routine check')
    print(json.dumps(dict(passed=True, cases=results, rom_sha256=hashlib.sha256(rom).hexdigest(),
                         symbols_sha256=hashlib.sha256(args.symbols.read_bytes()).hexdigest(),
                         helper=f'{entry:06X}', runner_copy_padding_bytes=padding, stubs=[],
                         claim='actual compiled helper/allocator on Yaze CPU; private RAM fixtures; '
                               'no SNES system timing, natural placement or route acceptance'), indent=2))


if __name__ == '__main__':
    main()
