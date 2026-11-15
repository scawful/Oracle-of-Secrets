#!/usr/bin/env python3
"""CPU-only watch-log lifecycle proof in an explicitly synthetic ROM.

Copy only the existing native text-engine region into an otherwise FF-filled
image, then assemble the production hook. No game ROM copy is patched. Native
initialization, choice redraw, terminator and finalization execute real bytes;
ParseMessage/VWF/window setup are explicit RTS stubs (not PPU/text proof).
The artificial target $1234 allocates no real message or story text.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from d4_compiled_fight_check import Cpu, Fixture


ROOT = Path(__file__).resolve().parents[1]
TARGET = 0x1234
STATE = 0x1CEB
LEARNED = 0x7EF3B2
SWORD = 0x7EF359


class TextFixture(Fixture):
    def read(self, address):
        # These are near-call RTS routines, not the Fixture's JSL/RTL stubs.
        if address in (0x0EC4C9, 0x0EC4E2, 0x0ED280, 0x0ED1F9):
            return 0x60
        return super().read(address)


def run_to(fixture, start, stop):
    cpu = fixture.cpu
    cpu.k, cpu.pc = start >> 16, start & 0xFFFF
    stack = cpu.sp
    for _ in range(12000):
        if (cpu.k << 16 | cpu.pc) == stop:
            assert cpu.sp == stack, ('stack', hex(start), cpu.sp, stack)
            assert not fixture.bad_writes, fixture.bad_writes
            return
        fixture.lib.cpu_runOpcode(fixture.p)
    raise AssertionError(('instruction bound', hex(cpu.k << 16 | cpu.pc)))


def cpu_state(f):
    return tuple(getattr(f.cpu, n) for n in
                 ('a', 'x', 'y', 'sp', 'dp', 'db', 'c', 'z', 'v', 'n',
                  'i', 'd', 'xf', 'mf'))


def assemble(directory, base, source, enabled=True, binding=TARGET):
    directory.mkdir()
    image = directory / 'synthetic.sfc'
    image.write_bytes(base)
    asm = directory / 'synthetic.asm'
    asm.write_text('lorom\n!ENABLE_SPECIAL_OVERWORLD_SOARING = %d\n'
                   '!SKY_SOARING_WATCH_LOG_MESSAGE = $%04X\n'
                   'SkySoaringLearned = $7EF3B2\n!SKY_SOARING_LEARNED = $A5\n'
                   'Sword = $7EF359\n'
                   'org $2B9000\nif !ENABLE_SPECIAL_OVERWORLD_SOARING == 1\n'
                   'incsrc "%s"\nendif\n' %
                   (enabled, binding, source.as_posix()))
    result = subprocess.run(['asar', '--no-title-check', '--fix-checksum=off',
                             '--symbols=wla', str(asm), str(image)],
                            capture_output=True, text=True)
    return result, image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-rom', type=Path, required=True)
    parser.add_argument('--lakesnes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference = args.reference_rom.read_bytes()
    synthetic = bytearray(b'\xFF' * 0x180000)
    start, end = 0x74440, 0x75400  # $0E:C440-$0E:D3FF only
    synthetic[start:end] = reference[start:end]
    cases = []
    with tempfile.TemporaryDirectory(prefix='sky-watch-log-cpu-') as temporary:
        temp = Path(temporary)
        source = ROOT / 'Items/sky_watch_log.asm'
        for enabled, binding, name in ((False, TARGET, 'inactive'),
                                       (True, 0xFFFF, 'unbound')):
            result, image = assemble(temp/name, synthetic, source, enabled, binding)
            assert result.returncode == 0, result.stdout + result.stderr
            assert image.read_bytes() == synthetic, name
            cases.append(name + '-no-emission')
        result, _ = assemble(temp/'helper', synthetic, source, True, 0x0009)
        assert result.returncode != 0 and 'explicit non-helper' in result.stderr
        cases.append('helper-binding-refused')
        changed_hook = bytearray(synthetic)
        changed_hook[0x744A4] ^= 1
        result, _ = assemble(temp/'changed-hook', changed_hook, source)
        assert result.returncode != 0 and 'initialization ABI moved' in result.stderr
        cases.append('changed-native-hook-refused')
        result, image = assemble(temp/'bound', synthetic, source)
        assert result.returncode == 0, result.stdout + result.stderr
        compiled = image.read_bytes()
        symbols = image.with_suffix('.sym').read_text()
        labels = {m[3]: int(m[1]+m[2], 16) for m in
                  re.finditer(r'(?m)^([\dA-Fa-f]{2}):([\dA-Fa-f]{4}) (\S+)$', symbols)}
        libpath = temp/'cpu.dylib'
        subprocess.run(['cc', '-shared', '-fPIC', '-O2',
                        str(args.lakesnes/'snes/cpu.c'),
                        str(args.lakesnes/'snes/statehandler.c'), '-o', str(libpath)],
                       check=True)
        lib = C.CDLL(str(libpath))
        lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        lib.cpu_free.argtypes = [C.POINTER(Cpu)]

        def fresh(body=compiled, message=TARGET):
            f = TextFixture(lib, body, labels)
            f.cpu.db = 0x0E
            f.cpu.a, f.cpu.x, f.cpu.y = 0xAB37, 0x56, 0x78
            f.cpu.c = f.cpu.v = True
            for address, value in ((0x10, 0x0E), (0x11, 2), (0x010C, 0x0B),
                                   (0x1B, 0), (LEARNED, 0), (STATE, 0xFF),
                                   (SWORD, 4)):
                f.put(address, value)
            f.word(0x1CF0, message)
            return f

        def initialize(f):
            run_to(f, 0x0EC491, 0x0EC4A9)
            assert not f.cpu.mf and not f.cpu.xf and f.cpu.a == 0x387F
            # The remainder of native initialization returns to M8/X8.
            f.cpu.mf = f.cpu.xf = True

        def acknowledge(f, pad=0x80, delay=0):
            f.put(0x1CE9, delay)
            f.put(0xF4, pad)
            f.put(0xF6, 0)
            run_to(f, 0x0ED25B, 0x0ED27F)

        def finalize(f):
            run_to(f, 0x0ECA61, 0x0ECA6B)
            assert f.get(STATE) == 0 and f.get(0x1CD8) == 0
            assert f.get(0x11) == 0 and f.get(0x10) == f.get(0x010C)

        for message in (TARGET, TARGET ^ 0x100, 9, 10):
            f, control = fresh(message=message), fresh(synthetic, message)
            run_to(f, 0x0EC491, 0x0EC4A9)
            run_to(control, 0x0EC491, 0x0EC4A9)
            assert cpu_state(f) == cpu_state(control), ('initialize ABI', message)
            assert f.get(STATE) == int(message == TARGET)
            assert all(a == STATE or 0x100 <= a < 0x200 or x == y for a, (x, y)
                       in enumerate(zip(f.ram, control.ram))), 'initialize collateral'
            cases.append('initialize-identity-%04x' % message)
            f.close(); control.close()

        for address, value in ((0x10, 7), (0x11, 3), (0x1B, 1), (0x010C, 9)):
            f = fresh(); f.put(address, value); initialize(f)
            assert f.get(STATE) == 0
            cases.append('initialize-context-%04x' % address); f.close()

        # Oracle's pedestal sword is exactly L4; lower and unknown values
        # cannot capture a conversation, even if upgraded before its close.
        for sword in (0, 1, 2, 3, 4, 5, 0xFF):
            f, control = fresh(), fresh(synthetic)
            for q in (f, control):
                q.put(SWORD, sword)
                run_to(q, 0x0EC491, 0x0EC4A9)
            assert cpu_state(f) == cpu_state(control), ('sword capture ABI', sword)
            assert f.get(STATE) == int(sword == 4), ('sword capture', sword)
            f.cpu.mf = f.cpu.xf = True
            f.put(SWORD, 4)
            acknowledge(f); finalize(f)
            assert f.get(LEARNED) == (0xA5 if sword == 4 else 0)
            cases.append('capture-sword-%02x-then-L4-close' % sword)
            f.close(); control.close()

        # A valid original read must still satisfy progression at final grant.
        for sword in (0, 1, 2, 3, 5, 0xFF):
            f, control = fresh(), fresh(synthetic)
            for q in (f, control):
                initialize(q); acknowledge(q)
            assert f.get(STATE) == 2
            for q in (f, control):
                q.put(STATE, 2); q.put(SWORD, sword)
            f.writes.clear()
            run_to(f, 0x0ECA61, 0x0ECA6B)
            run_to(control, 0x0ECA61, 0x0ECA6B)
            assert cpu_state(f) == cpu_state(control), ('sword grant ABI', sword)
            assert f.get(STATE) == 0 and f.get(LEARNED) == 0
            assert not [w for w in f.writes if w[0] == LEARNED]
            cases.append('close-required-sword-lost-%02x' % sword)
            f.close(); control.close()

        for previous, pad, helper in ((0, 4, 10), (1, 8, 9)):
            f = fresh(); initialize(f)
            assert f.get(LEARNED) == 0 and f.get(STATE) == 1
            f.put(0x1CE9, 0); f.put(0x1CE8, previous); f.put(0xF4, pad)
            run_to(f, 0x0ECF72, 0x0ECFD6)
            assert f.get(0x1CF0) == helper and f.get(STATE) == 1
            acknowledge(f)
            assert f.get(STATE) == 2 and f.get(LEARNED) == 0
            finalize(f)
            assert f.get(LEARNED) == 0xA5
            cases.append('native-helper-%02x-then-complete' % helper); f.close()

        for pad, delay in ((0, 0), (0x80, 2), (0x80, 1)):
            f = fresh(); initialize(f); acknowledge(f, pad, delay)
            assert f.get(STATE) == 1 and f.get(LEARNED) == 0
            cases.append('unfinished-delay-%d-input-%02x' % (delay, pad)); f.close()

        f, control = fresh(), fresh(synthetic)
        for q in (f, control):
            q.put(STATE, 1); q.put(0xF4, 0x80); q.put(0x1CE9, 0)
            run_to(q, 0x0ED25B, 0x0ED27F)
        assert cpu_state(f) == cpu_state(control), 'acknowledge displaced ABI'
        assert f.get(STATE) == 2 and control.get(STATE) == 1
        cases.append('native-terminator-acknowledge-ABI'); f.close(); control.close()

        for selection in (0, 1):
            f = fresh(); initialize(f)
            f.put(0x1CE9, 0); f.put(0x1CE8, selection); f.put(0xF4, 0x10)
            run_to(f, 0x0ECF72, 0x0ECFE1)
            assert f.get(STATE) == 1 and f.get(0x1CD4) == 4
            finalize(f)
            assert f.get(LEARNED) == 0
            cases.append('choice-close-without-terminator-%d' % selection); f.close()

        for learned in (0, 1, 0xA4, 0xA5, 0xFF):
            f, control = fresh(), fresh(synthetic)
            for q in (f, control):
                q.put(STATE, 2); q.put(LEARNED, learned)
            before = bytes(f.ram)
            f.writes.clear()
            run_to(f, 0x0ECA61, 0x0ECA6B)
            run_to(control, 0x0ECA61, 0x0ECA6B)
            assert cpu_state(f) == cpu_state(control), ('finalize ABI', learned)
            assert f.get(LEARNED) == 0xA5
            allowed = {STATE, LEARNED-0x7E0000, 0x10, 0x11, 0x1CD8}
            assert all(a in allowed or 0x100 <= a < 0x200 or x == y
                       for a, (x, y) in enumerate(zip(before, f.ram))), 'save collateral'
            writes = [w for w in f.writes if w[0] == LEARNED]
            assert len(writes) == (0 if learned == 0xA5 else 1)
            f.put(0x10, 0x0E); f.put(0x11, 2)
            finalize(f)
            assert [w for w in f.writes if w[0] == LEARNED] == writes
            cases.append('token-%02x-and-repeat' % learned)
            f.close(); control.close()

        for address, value in ((0x10, 7), (0x11, 3), (0x1B, 1), (0x010C, 9)):
            f = fresh(); initialize(f); acknowledge(f); f.put(address, value)
            finalize(f)
            assert f.get(LEARNED) == 0
            cases.append('close-context-refused-%04x' % address); f.close()
        f = fresh(); initialize(f)
        f.word(0x1CF0, TARGET ^ 0x100); initialize(f)
        acknowledge(f); finalize(f)
        assert f.get(LEARNED) == 0
        cases.append('interrupted-then-unrelated-conversation'); f.close()

    result = {'passed': True, 'case_count': len(cases), 'cases': cases,
              'reference_rom_sha256': hashlib.sha256(reference).hexdigest(),
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'scope': 'Synthetic compiled CPU lifecycle/ABI only; no native text, teaching site, saved-file or travel proof.'}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
