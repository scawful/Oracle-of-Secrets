#!/usr/bin/env python3
"""Run compiled Ice Rod contact/stripe code on Yaze's CPU, without game writes.

Disposable ROM fixtures change DATA only (dictionary, resident rows, attributes
and membership); every executed instruction/callee comes from the supplied ROM.
This is CPU/ABI/queue proof, not PPU timing or a native border reproduction.
The old control alone gets a synthetic VBlank MMIO value to finish its DMA loop.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
WRAM, SP = 0x7E0000, 0x1FFF


def pc(address):
    return ((address >> 16) & 127) * 0x8000 + (address & 0x7FFF)


def constants(path):
    return {name: int(value, 16) for name, value in re.findall(
        r'^!(\w+)\s*=\s*\$([0-9A-Fa-f]+)', path.read_text(), re.M)}


def word(data, offset, value):
    data[offset:offset + 2] = value.to_bytes(2, 'little')


def cases(sky_types=False):
    # Expected cells come from the native buffer's documented quadrant bits,
    # not a Python copy of the ASM coordinate formula.
    rows = [
        dict(name='ordinary-water', page=2, y=0x108, x8=0x20, cell=0x820, freeze=True),
        dict(name='ordinary-mixed-vine', page=2, y=0x108, x8=0x20, cell=0x820,
             global_vine=True, freeze=False),
        dict(name='resident-vine-global-water', page=0x90, y=0x108, x8=0x20,
             cell=0x820, resident_vine=0x90, freeze=False),
        dict(name='resident-water-global-vine', page=0x90, y=0x108, x8=0x20,
             cell=0x820, global_vine=True, freeze=True),
        dict(name='sample-right-page-not-link-page', page=0x90, y=0x108, x8=0x60,
             cell=0x860, resident_vine=0x91, freeze=False),
        dict(name='sample-lower-page', page=0x90, y=0x308, x8=0x20,
             cell=0x1820, resident_vine=0x98, freeze=False),
        dict(name='sample-lower-right-page', page=0x90, y=0x308, x8=0x60,
             cell=0x1860, resident_vine=0x99, freeze=False),
        dict(name='masked-area-wrap', page=0x90, y=0x508, x8=0xA0,
             cell=0x820, freeze=True),
        dict(name='nonzero-origin-left-edge', page=0x90, y=0x1008, x8=0x200,
             origin_y=0x1000, origin_x8=0x200, cell=0, freeze=True),
        dict(name='last-right-cell', page=0x90, y=0x108, x8=0x7E,
             cell=0x87E, freeze=True),
        dict(name='first-wrapped-right-cell', page=0x90, y=0x108, x8=0x80,
             cell=0x800, freeze=True),
        dict(name='missing-resident-ice-row', page=0x90, y=0x108, x8=0x20,
             cell=0x820, missing_ice=True, freeze=False),
        dict(name='changed-resident-ice-word', page=0x90, y=0x108, x8=0x20,
             cell=0x820, changed_ice=True, freeze=False),
        dict(name='sparse-source-fallback', page=0x90, y=0x108, x8=0x20,
             cell=0x820, missing_source=True, freeze=True),
        dict(name='full-stripe-queue', page=2, y=0x108, x8=0x20, cell=0x820,
             queue=0xF0, freeze=False),
        dict(name='append-pending-stripe', page=2, y=0x108, x8=0x20, cell=0x820,
             queue=0x20, mode=1, freeze=True),
        dict(name='last-fitting-stripe', page=2, y=0x108, x8=0x20, cell=0x820,
             queue=0xE0, freeze=True),
        dict(name='other-stripe-mode', page=2, y=0x108, x8=0x20, cell=0x820,
             mode=3, freeze=False),
        dict(name='indoor-coordinate-domain', page=2, y=0x108, x8=0x20,
             cell=0x820, indoors=1, freeze=False),
        dict(name='second-shot-unchanged', page=2, y=0x108, x8=0x20,
             cell=0x820, slot=3, freeze=False),
        dict(name='invalid-tile16', page=2, y=0x108, x8=0x20,
             cell=0x820, tile=0x1000, freeze=False),
    ]
    if sky_types:
        rows += [dict(name=f'sky-quarter-domain-{page:02x}', page=page,
                      y=0x108, x8=0x20, cell=0x820, sky_quarter=True,
                      freeze=False) for page in (0x84, 0x8C)]
    return rows


def fixture(original, bindings, case):
    image = bytearray(original)
    dictionary = pc(bindings['LYRA_CURRENT_MAP16_DEFINITIONS'])
    water = [0x19E4, 0x59E4, 0x99E4, 0xD9E4]  # flips do not change attribute
    if case.get('sky_quarter'):
        water[1] = 0x188B  # native type08 versus selected Sky type48
    source = water.copy()
    if case.get('global_vine'):
        source[3] = 0x19C8
    for q, value in enumerate(source):
        word(image, dictionary + 0x200 * 8 + q * 2, value)
        word(image, dictionary + 0xB7 * 8 + q * 2, 0x1D83)
    image[pc(0x0E9459) + 0x1E4] = 8
    image[pc(0x0E9459) + 0x1C8] = 2
    image[pc(0x0E9459) + 0x08B] = 8
    # Use the existing ABI's real directory, with disposable data in bank CE.
    # These fixture placements confer no production allocation.
    directory = pc(bindings['LYRA_CURRENT_RESIDENT_DIRECTORY'])
    for i, page in enumerate((0x90, 0x91, 0x98, 0x99, 0x84, 0x8C)):
        index_at, words_at = 0xCE9000 + i * 0x200, 0xCEA000 + i * 0x100
        index = bytearray(192)
        index[0x200 >> 5] = 1
        index[0xB7 >> 5] = 2
        if not case.get('missing_source'):
            index[128] = 1
        if not case.get('missing_ice'):
            index[160 + (0xB7 & 31)] = 2
        image[pc(index_at):pc(index_at) + len(index)] = index
        words = bytearray(24)
        for q, value in enumerate(water):
            if page == case.get('resident_vine') and q == 3:
                value = 0x19C8
            word(words, 8 + q * 2, value)
            word(words, 16 + q * 2, 0x1D84 if case.get('changed_ice') else 0x1D83)
        image[pc(words_at):pc(words_at) + len(words)] = words
        at = directory + (page - 0x80) * 8
        image[at:at + 8] = (index_at.to_bytes(3, 'little') +
                            words_at.to_bytes(3, 'little') + bytes([1, 2]))
        image[pc(bindings['LYRA_CURRENT_TABLE_parent']) + page] = 0x90 if i < 4 else page
        image[pc(bindings['LYRA_CURRENT_TABLE_area_size']) + page] = 1 if i < 4 else 0
    ram = bytearray(0x20000)
    # Nonzero scratch exposes accidental corruption by the mutable renderer.
    ram[:16] = bytes(range(0xA0, 0xB0))
    word(ram, 0, case['y'])
    word(ram, 2, case['x8'])
    word(ram, 0x708, case.get('origin_y', 0))
    word(ram, 0x70A, 0x3F0)
    word(ram, 0x70C, case.get('origin_x8', 0))
    word(ram, 0x70E, 0x7E)
    word(ram, 0x8A, case['page'])
    ram[0x8C] = 1
    ram[0x1B] = case.get('indoors', 0)
    ram[0x3A3] = ram[0x303] = ram[0x304] = 6
    ram[0x3E8] = 8
    ram[0x14] = case.get('mode', 0)
    word(ram, 0x1000, case.get('queue', 0))
    word(ram, 0x2000 + case['cell'], case.get('tile', 0x200))
    request = dict(entry=0x0EFBA0, reset_ram=True,
                   registers=dict(a=0xA508, x=case.get('slot', 4), y=0x77,
                                  p=0x38, db=8, d=0, sp=SP),
                   writes=[dict(address=WRAM, bytes=list(ram))],
                   reads=[dict(address=WRAM, length=len(ram))],
                   trace_writes=True, trace_mmio=True, max_steps=10000)
    return image, ram, request


def verify(case, before, result, control):
    if not result.get('returned'):
        raise AssertionError(f"{case['name']}: {result.get('error')}")
    after = bytes(result['reads'][0]['bytes'])
    actual = int.from_bytes(after[0x2000 + case['cell']:0x2002 + case['cell']], 'little')
    expected = 0xB7 if case['freeze'] else case.get('tile', 0x200)
    matches = actual == expected
    if not control:
        assert matches, (case['name'], hex(actual), hex(expected))
        regs = result['registers']
        assert (regs['x'], regs['y'], regs['sp'], regs['db'], regs['d']) == (
            case.get('slot', 4), 8, SP, 8, 0), (case['name'], regs)
        assert regs['p'] & 0x38 == 0x38 and regs['a'] & 0xFF00 == 0xA500
        assert not result.get('mmio_writes'), 'Contact must queue, not perform DMA'
        allowed = ({0x3E4 + case.get('slot', 4)} | set(range(0x1F80, 0x2000))
                   | set(range(0x18000, 0x18004)))  # runner's real JSL trampoline
        if case['freeze']:
            allowed |= {0x14, 0x2000 + case['cell'], 0x2001 + case['cell']}
            queue = case.get('queue', 0)
            allowed |= {0x1000, 0x1001} | set(range(0x1002 + queue, 0x1014 + queue))
            assert after[0x14] == 1 and int.from_bytes(after[0x1000:0x1002], 'little') == queue + 16
            assert [int.from_bytes(after[i+queue:i+queue+2], 'little') for i in (0x1006, 0x1008, 0x100E, 0x1010)] == [0x1D83] * 4
            # Known ring-buffer boundary addresses, independent of the ASM
            # bit-manipulation formula: x31 -> x0 crosses $0C1E -> $0800.
            top = {0: 0, 0x820: 0xC00, 0x87E: 0xC1E, 0x800: 0x800}[case['cell']]
            assert int.from_bytes(after[0x1002+queue:0x1004+queue], 'big') == top
            assert int.from_bytes(after[0x100A+queue:0x100C+queue], 'big') == top + 0x20
        assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(before, after))), case['name']
    return dict(name=case['name'], expected_tile16=expected, actual_tile16=actual,
                matches=matches, steps=result['steps'], registers=result['registers'],
                mmio_write_count=len(result.get('mmio_writes', [])))


def query_abi(original, bindings, symbols, runner, rom):
    match = re.search(r'^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?'
                      r'Lyra_ResidentReadTerrainWord$', symbols.read_text(), re.M)
    assert match, 'Missing exported query symbol'
    entry = int(''.join(match.groups()), 16)
    results = []
    for resident in (False, True):
        case = dict(name='query-abi', page=0x90 if resident else 2,
                    y=0x108, x8=0x60, cell=0x860, resident_vine=0x91)
        image, before, request = fixture(original, bindings, case)
        request['entry'] = entry
        request['registers'] = dict(a=0xA55A, x=0x860, y=0x1006,
                                    p=8, db=0x42, d=0x1234, sp=SP)
        rom.write_bytes(image)
        run = subprocess.run([str(runner.resolve()), str(rom)],
                             input=json.dumps(request) + '\n', text=True,
                             capture_output=True, check=True, timeout=20)
        result = json.loads(run.stdout)
        assert result.get('returned'), result.get('error')
        regs = result['registers']
        assert (regs['x'], regs['db'], regs['d'], regs['sp'], regs['p'] & 0x38) == (0x860, 0x42, 0x1234, SP, 8), regs
        assert (regs['a'], regs['y'], regs['p'] & 1) == ((0x19C8, 0x91, 1) if resident else (0xD9E4, 0xFFFF, 0)), regs
        after = bytes(result['reads'][0]['bytes'])
        allowed = set(range(0x1F80, 0x2000)) | set(range(0x18000, 0x18004))
        assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(before, after)))
        results.append(dict(resident=resident, passed=True, registers=regs))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--cpu-runner', type=Path, required=True)
    parser.add_argument('--constants', type=Path, default=ROOT / '.cache/special_overworld_reader_constants.asm')
    parser.add_argument('--expect-control', action='store_true')
    parser.add_argument('--symbols', type=Path)
    parser.add_argument('--sky-types', action='store_true')
    parser.add_argument('--resident-disabled', action='store_true')
    args = parser.parse_args()
    original = args.rom.read_bytes()
    bindings = constants(args.constants)
    results = []
    with tempfile.TemporaryDirectory(prefix='ice-rod-context-') as folder:
        rom = Path(folder) / 'data-fixture.sfc'
        for case in cases(args.sky_types):
            if args.resident_disabled and case['page'] >= 0x80:
                case['freeze'] = False  # no explicit ice binding in this variant
            image, before, request = fixture(original, bindings, case)
            rom.write_bytes(image)
            if args.expect_control:
                request['mmio'] = [dict(address=a, value=v) for a, v in [(0x4212, 0x80)] + [(a, 0) for a in (0x2116, 0x2117, 0x420B, *range(0x4300, 0x4307))]]
            run = subprocess.run([str(args.cpu_runner.resolve()), str(rom)],
                                 input=json.dumps(request) + '\n', text=True,
                                 capture_output=True, check=True, timeout=20)
            results.append(verify(case, before, json.loads(run.stdout), args.expect_control))
        abi = query_abi(original, bindings, args.symbols, args.cpu_runner, rom) if args.symbols else []
    failures = [r['name'] for r in results if not r['matches']]
    if args.expect_control:
        assert 'resident-vine-global-water' in failures and 'resident-water-global-vine' in failures
    assert args.rom.read_bytes() == original
    print(json.dumps(dict(passed=True, role='control' if args.expect_control else 'candidate',
                         rom_sha256=hashlib.sha256(original).hexdigest(), cases=results,
                         expected_control_failures=failures,
                         query_abi=abi,
                         scope='Compiled CPU/data/stripe ABI; synthetic map data; no native border or PPU timing proof',
                         instruction_stubs=[]), indent=2))


if __name__ == '__main__':
    main()
