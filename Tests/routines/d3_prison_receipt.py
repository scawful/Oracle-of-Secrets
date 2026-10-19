#!/usr/bin/env python3
"""Run native chest receipt completion through the compiled D3 arm hook.

Starts after item text has finished, using real $08C515 instructions and their
native cleanup. Synthetic WRAM is not evidence of chest interaction or dialogue.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from d3_prison_state import (ARM, FLAGS, SAVE, SP, WRAM, Case, digest,
                             fixture, physical, require, symbol)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--symbols', type=Path, required=True)
    p.add_argument('--cpu-runner', type=Path, required=True)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    inputs = {path: path.read_bytes() for path in
              (args.rom, args.symbols, args.cpu_runner)}
    rom = inputs[args.rom]
    require(0 < len(rom) <= 0x400000 and len(rom) % 0x8000 != 0x200,
            'Expected headerless LoROM <=4 MiB')
    target = symbol(inputs[args.symbols].decode(), ARM)
    def code(pc, expected):
        offset = (pc >> 16) * 0x8000 + (pc & 0x7FFF)
        require(rom[offset:offset + len(expected)] == expected,
                f'Native path byte contract changed at ${pc:06X}')
    code(0x08C43B, b'\x22' + target.to_bytes(3, 'little') + b'\xEA\xEA')
    code(0x08C42C, bytes.fromhex('84 5D 9C D8 02 9C DA 02 9C 7B 03'))
    code(0x08C515, bytes.fromhex('DE B1 03 BD B1 03 10 03 82 1B FF'))
    cases = (
        Case('native-chest-arms-after-text', ARM, 0x80, 2, 0x84, 2, None),
        Case('native-other-item-does-not-arm', ARM, 0x80, 2, 0x80, 2, None, item=2),
        Case('native-escaped-receipt-does-not-rearm', ARM, 0x82, 2, 0x82, 2, None),
    )
    plans = []
    for case in cases:
        low, save, request = fixture(case, 0x080E00)
        # Same-bank real JSR/RTL wrapper for the native RTS routine; no stubs.
        low[0xE00:0xE04] = bytes.fromhex('20 15 C5 6B')
        x = request['registers']['x']
        for offset, value in ((0x3B1 + x, 0), (0xC54 + x, 1),
                              (0xC4A + x, 0x22), (0x2E9, 1),
                              (0x2E4, 1), (0xFC1, 1)):
            low[offset] = value
        request['registers'].update(p=0x34, db=8)
        request['writes'][0]['bytes'] = list(low)
        plans.append((case, low, save, request))
    padding = (-len(rom)) % 0x8000
    with tempfile.TemporaryDirectory(prefix='d3-receipt-') as directory:
        copy = Path(directory) / 'candidate.sfc'
        copy.write_bytes(rom + b'\xFF' * padding)
        run = subprocess.run([str(args.cpu_runner), str(copy)],
                             input=''.join(json.dumps(v[3]) + '\n' for v in plans),
                             text=True, capture_output=True, check=True, timeout=20)
    lines = run.stdout.splitlines()
    require(len(lines) == len(plans), 'Wrong number of CPU runner results')
    results = []
    for (case, low, save, request), line in zip(plans, lines):
        result = json.loads(line)
        require(result.get('returned'), f"{case.name}: {result.get('error')}")
        require(not result.get('stub_calls') and not result.get('mmio_writes'),
                f'{case.name}: unexpected stub/device access')
        regs = result['registers']
        for key in ('x', 'y', 'db', 'd', 'sp'):
            require(regs[key] == request['registers'][key], f'{case.name}: ABI {key}')
        require(regs['a'] == 0xBE01 and regs['p'] == 0xB4 and regs['e'] == 0,
                f'{case.name}: native completion result/status mismatch')
        x = regs['x']
        expected_low, expected_save = bytearray(low), bytearray(save)
        changed = {0x3B1+x: 0xFF, 0x2E9: 0, 0xC4A+x: 0, 0xFC1: 0, 0x2E4: 0}
        for offset, value in changed.items():
            expected_low[offset] = value
        expected_save[FLAGS-SAVE] = case.expected_flags
        allowed = {WRAM+v for v in changed}
        if case.expected_flags != case.flags:
            allowed.add(FLAGS)
        allowed.update(range(WRAM+SP-0x20, WRAM+SP+1))
        allowed.update(range(0x7F8000, 0x7F8004))
        after_low, after_save = (bytes(v['bytes']) for v in result['reads'])
        require(after_save == expected_save, f'{case.name}: save canary mismatch')
        for offset, (actual, wanted) in enumerate(zip(after_low, expected_low)):
            if not SP-0x20 <= offset <= SP:
                require(actual == wanted, f'{case.name}: WRAM ${offset:04X}')
        writes = {physical(v['address']) for v in result.get('writes', [])}
        require(writes <= allowed, f'{case.name}: undeclared writes {writes-allowed}')
        require(all(WRAM+v in writes for v in changed), f'{case.name}: cleanup missing')
        if case.expected_flags != case.flags:
            require(FLAGS in writes, f'{case.name}: arm store missing')
        results.append(dict(name=case.name, passed=True, steps=result['steps'],
                            flags_before=case.flags, flags_after=case.expected_flags))
    require(all(path.read_bytes() == data for path, data in inputs.items()),
            'Input changed during CPU check')
    output = dict(passed=True, cases=results, case_count=len(results), stubs=[],
                  input_sha256={str(path): digest(data) for path,data in inputs.items()},
                  script_sha256=digest(Path(__file__).read_bytes()),
                  runner_copy_padding_bytes=padding,
                  claim='Actual native chest completion and cleanup; synthetic WRAM, '
                        'not native chest opening or Farore dialogue acceptance.')
    if args.output:
        require(args.output.resolve() not in {v.resolve() for v in inputs},
                'Output must not overwrite input')
        args.output.write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
