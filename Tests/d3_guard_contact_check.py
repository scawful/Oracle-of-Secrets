#!/usr/bin/env python3
"""Execute compiled guard scope checks with the existing Lakesnes CPU fixture.

Native contact/hitbox code and the capture routine run unchanged. The sprite's
native $0E40 bit7 selects overlap-only contact, avoiding unrelated damage effects.
This is CPU/ABI evidence with seeded state, not native guard gameplay proof.
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


def labels(path, root):
    out = {m[3]: int(m[1]+m[2], 16) for m in re.finditer(
        r'(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)$', path.read_text())}
    out.update({n: int(v, 16) for n, v in re.findall(
        r'(?m)^(\w+)\s*=\s*\$([0-9A-Fa-f]+)', (root/'Core/symbols.asm').read_text())})
    out['NativeGuardContact'] = 0x06F121
    return out


def fresh(lib, rom, syms, indoor=1, dungeon=0x10, subtype=5, minish=0,
          overlap=True, alert=0, captured=0, stagger=False, db=5, carry=False):
    f = Fixture(lib, rom, syms)
    f.stubs.clear()  # Execute actual native contact and capture bytes.
    slot = 6
    for address, value in ((0x1B, indoor), (0x40C, dungeon), (0x02B2, minish),
                           (syms['SprSubtype']+slot, subtype), (0x0FDC, alert),
                           (0x7EF306, 0xA4|captured), (0x7EF3C8, 0x71),
                           (0x10, 7), (0x11, 0), (0x7EF359, 2),
                           (0x1A, slot if not stagger else slot^1),
                           (0x0E40+slot, 0x80), (0x7EF3C5, 2)):
        f.put(address, value)
    f.word(0x10E, 0xCAFE)
    f.word(0x22, 128 if overlap else 256); f.word(0x20, 128)
    f.word(0x0FD8, 128); f.word(0x0FDA, 128)
    f.cpu.a = 0xAB5C; f.cpu.y = 0x42; f.cpu.db = db
    f.cpu.c = carry; f.cpu.v = True; f.cpu.i = True
    return f


def run(f, name):
    f.call(name, x=6, a=0x5C, long_return=True)
    assert not f.calls and not f.bad_writes, ('Unintended engine stub/write', f.calls, f.bad_writes)
    assert f.cpu.sp == 0x1FF and f.cpu.dp == 0 and f.cpu.mf and f.cpu.xf
    return f


def same_result(a, b, context):
    attrs = ('a', 'x', 'y', 'sp', 'dp', 'db', 'c', 'z', 'v', 'n', 'i', 'd', 'xf', 'mf')
    assert all(getattr(a.cpu, n) == getattr(b.cpu, n) for n in attrs), (context, 'CPU ABI')
    assert all(0x100 <= i < 0x200 or x == y for i, (x, y) in enumerate(zip(a.ram, b.ram))), (context, 'non-stack RAM')


def check(lib, rom, syms, control, control_syms):
    count = 0
    # Both native carry outcomes, alert set/clear, frame staggering, each prison
    # subtype, both forms, outdoors and two wrong dungeon IDs, and both callers.
    for indoor, dungeon in ((0, 0x10), (1, 0x0A), (1, 0x12)):
        for subtype in (5, 6, 7):
            for minish in (0, 5):
                for overlap, alert, stagger in ((True, 0, False), (False, 0, False),
                                                 (True, 0x5A, False), (True, 0x5A, True)):
                    values = dict(indoor=indoor, dungeon=dungeon, subtype=subtype,
                                  minish=minish, overlap=overlap, alert=alert,
                                  stagger=stagger, db=0x7E if count&1 else 5, carry=bool(count&2))
                    for entry in ('Guard_CheckDamageToLink_CaptureWrapper', 'IntroPatrol_GuardContact'):
                        a = run(fresh(lib, control, control_syms, **values), 'NativeGuardContact')
                        b = run(fresh(lib, rom, syms, **values), entry)
                        same_result(a, b, (values, entry))
                        assert b.get(0x7EF306) == 0xA4 and b.get(0x7EF3C8) == 0x71
                        assert b.get(0x10) == 7 and b.get(0x0FDC) == alert
                        for f in (a, b): f.close()
                        count += 1
    # D3 behavior must remain identical to the admitted old wrapper, including
    # ordinary subtypes and one-shot capture. No old source is rebuilt.
    inside = 0
    for subtype in (0, 4, 5, 6, 7):
        for minish in (0, 5):
            for captured in (0, 1):
                values = dict(subtype=subtype, minish=minish, captured=captured, alert=0x5A)
                a = run(fresh(lib, control, control_syms, **values), 'Guard_CheckDamageToLink_CaptureWrapper')
                b = run(fresh(lib, rom, syms, **values), 'Guard_CheckDamageToLink_CaptureWrapper')
                same_result(a, b, values)
                if subtype >= 5 and minish == 5:
                    assert not b.cpu.c and b.get(0x0FDC) == 0 and b.get(0x10) == 7
                elif subtype >= 5 and not captured:
                    assert b.get(0x10) == 5 and b.get(0x10E) == 0x32 and b.get(0x10F) == 0
                    assert b.get(0x7EF306) == 0xA5 and b.get(0x7EF3C8) == 2
                    assert not b.cpu.c and b.get(0x0FDC) == 0
                else:
                    assert b.get(0x10) == 7 and b.get(0x0FDC) == 0x5A
                for f in (a, b): f.close()
                inside += 1
    # Explicit failing-behavior controls on the immutable old ROM: outside D3,
    # Minish incorrectly suppresses contact; normal form incorrectly captures.
    for minish in (0, 5):
        f = run(fresh(lib, control, control_syms, dungeon=0x0A, minish=minish, alert=0x5A),
                'Guard_CheckDamageToLink_CaptureWrapper')
        assert f.get(0x0FDC) == 0
        assert f.get(0x10) == (5 if minish == 0 else 7)
        assert f.get(0x7EF306) == (0xA5 if minish == 0 else 0xA4)
        f.close()
    return dict(outside_native_equivalence=count, inside_legacy_equivalence=inside,
                old_rom_scope_defect_controls=2)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('rom', 'symbols', 'control-rom', 'control-symbols', 'lakesnes', 'output'):
        ap.add_argument('--'+name, type=Path, required=True)
    a = ap.parse_args(); assert not a.output.exists()
    root = Path(__file__).resolve().parents[1]
    rom, control = a.rom.read_bytes(), a.control_rom.read_bytes()
    syms, ctl_syms = labels(a.symbols, root), labels(a.control_symbols, root)
    with tempfile.TemporaryDirectory(prefix='d3-guard-cpu-') as temp:
        library = Path(temp)/'cpu.dylib'
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', str(a.lakesnes/'snes/cpu.c'),
                        str(a.lakesnes/'snes/statehandler.c'), '-o', str(library)], check=True)
        lib = C.CDLL(str(library)); lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]; lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        results = check(lib, rom, syms, control, ctl_syms)
    report = dict(status='COMPILED_CPU_FIXTURE_PASS', results=results,
                  rom_sha256=hashlib.sha256(rom).hexdigest(),
                  control_sha256=hashlib.sha256(control).hexdigest(),
                  scope='Actual native contact/hitbox and capture bytes, seeded overlap-only sprite, no engine stubs. Not native gameplay.')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2)+'\n'); print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
