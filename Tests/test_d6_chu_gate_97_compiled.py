#!/usr/bin/env python3
"""Bounded synthetic CPU proof for the inactive room97 Bombchu gate.

Production handlers are assembled into an FF image with only the native door
pointer/data bytes needed by their assertions. Native draw/save/load/animation
run from the read-only reference bytes separately. No game ROM is written;
render DMA and collision calls are explicit animation stubs, not native play.
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
REFERENCE_SHA = '17d3d61e0f2ba415d763bb9b160676468d828994c997131add9d1c1e56cd7744'


def pc(a):
    return ((a >> 16) & 0x7F) * 0x8000 + (a & 0x7FFF)


def word(f, a):
    return f.get(a) | f.get(a + 1) << 8


def block(text, label):
    start = text.index(label + ':')
    end = text.index('\n}', start) + 2
    return text[start:end] + '\n'


def assemble(directory, reference, enabled=True, corrupt=False):
    directory.mkdir()
    synthetic = bytearray(b'\xFF' * len(reference))
    pointer = int.from_bytes(reference[pc(0x01B6CC):pc(0x01B6CC)+3], 'little')
    door = int.from_bytes(reference[pc(pointer+0x97*3):pc(pointer+0x97*3)+3], 'little')
    for a, size in ((0x01B6CB, 4), (pointer+0x97*3, 3), (door, 6)):
        synthetic[pc(a):pc(a)+size] = reference[pc(a):pc(a)+size]
    if corrupt:
        synthetic[pc(door)+4] = 0x63  # a third/fourth-door allocation is forbidden
    image = directory/'synthetic.sfc'
    image.write_bytes(synthetic)
    symbols = (ROOT/'Core/symbols.asm').read_text()
    names = ('SprState', 'SprType', 'SprSubtype', 'SprFloor', 'SprX', 'SprY',
             'SprXH', 'SprYH', 'SprDefl', 'SprTileDie', 'SprBulletproof',
             'SprAction', 'SprFrame')
    defs = '\n'.join(re.search(r'(?m)^'+n+r'\s*=\s*\$[\dA-Fa-f]+', symbols)[0]
                     for n in names)
    bombchu = (ROOT/'Items/bombchu.asm').read_text()
    defs += '\n' + '\n'.join(re.findall(r'(?m)^Bombchu\w+\s*=\s*\$[\dA-Fa-f]+', bombchu))
    defs += '\n' + re.search(r'(?m)^BombchuOwned\s*=\s*\$[\dA-Fa-f]+',
                            (ROOT/'Core/sram.asm').read_text())[0] + '\n'
    # Compile the actual shared predicates, not a broadened test substitute.
    circuit = (ROOT/'Dungeons/d6_cart_circuit.asm').read_text()
    custom = block((ROOT/'Dungeons/custom_tag.asm').read_text(), 'CustomTag')
    (directory/'fixture.asm').write_text(
        'lorom\n!ENABLE_D6_CHU_GATE_97 = %d\n!ENABLE_DIVE_GATE = 0\n'
        '!DISABLE_MUSIC = 1\nRoomTag_Return = $2C7000\norg $2C9000\n' % enabled
        + defs + custom
        + 'D6CartCircuit_Main: RTS\nHouseTag_Main: RTS\n'
        + block(circuit, 'D6CartCircuit_IsRoom')
        + block(circuit, 'D6ChuActor_IsRoom')
        + block(circuit, 'D6ChuActor_IsLoadedRoom')
        + 'incsrc "%s"\n' % (ROOT/'Dungeons/d9_key_gate.asm').as_posix()
        + 'Sprite_LeverSwitch_Prep_Ordinary: RTL\n'
        + 'FixtureEnd:\nif !ENABLE_D6_CHU_GATE_97 == 1\norg $2BBE22\nincsrc "%s"\nFixtureGateEnd:\nendif\n' %
          (ROOT/'Dungeons/d6_chu_gate_97.asm').as_posix())
    result = subprocess.run(['asar', '--no-title-check', '--fix-checksum=off',
                             '--symbols=wla', str(directory/'fixture.asm'), str(image)],
                            capture_output=True, text=True)
    if result.returncode:
        return result, None, None
    labels = {m[3]: int(m[1]+m[2], 16) for m in re.finditer(
        r'(?m)^([\dA-Fa-f]{2}):([\dA-Fa-f]{4}) (\S+)$', image.with_suffix('.sym').read_text())}
    return result, image.read_bytes(), labels


def native_run(f, start, stop=None, long_return=False):
    c = f.cpu
    c.k, c.pc = start >> 16, start & 0xFFFF
    sp = c.sp
    if stop is None:
        stop = start & 0xFF0000 | 0x7000
        if long_return:
            f.put(c.sp, c.k); c.sp -= 1
        f.put(c.sp, 0x6F); f.put(c.sp-1, 0xFF); c.sp -= 2
    for count in range(30000):
        address = c.k << 16 | c.pc
        if address == stop:
            assert c.sp == sp and not f.bad_writes, (c.sp, sp, f.bad_writes)
            return count
        if address in getattr(f, 'near_stubs', {}):
            f.calls.append((address, c.y))
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(('native instruction bound', hex(c.k << 16 | c.pc)))


class NativeFixture(Fixture):
    # Only the three downstream animation consumers are stubbed. Their call
    # index is recorded; the native mask/type/animation decisions execute.
    near_stubs = {0x01D311: 'draw', 0x01F764: 'dma', 0x01D51C: 'collision'}

    def read(self, address):
        if address in self.near_stubs:
            return 0x60
        return super().read(address)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference-rom', required=True, type=Path)
    ap.add_argument('--lakesnes', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    reference = args.reference_rom.read_bytes()
    assert hashlib.sha256(reference).hexdigest() == REFERENCE_SHA, 'wrong frozen reference'
    cases = []
    with tempfile.TemporaryDirectory(prefix='goron97-cpu-') as temporary:
        temp = Path(temporary)
        result, compiled, labels = assemble(temp/'enabled', reference)
        assert result.returncode == 0, result.stdout + result.stderr
        result, disabled, off_labels = assemble(temp/'disabled', reference, False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'D6ChuGate97_Main' not in off_labels
        cases.append('disabled-no-gate-emission')
        result, _, _ = assemble(temp/'door-mismatch', reference, corrupt=True)
        assert result.returncode and 'exactly two doors' in result.stderr
        cases.append('changed-door-composition-refused')
        libpath = temp/'cpu.dylib'
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', str(args.lakesnes/'snes/cpu.c'),
                        str(args.lakesnes/'snes/statehandler.c'), '-o', str(libpath)], check=True)
        lib = C.CDLL(str(libpath))
        lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        lib.cpu_free.argtypes = [C.POINTER(Cpu)]

        def fresh(slot=0, body=compiled, symbols=labels):
            f = Fixture(lib, body, symbols)
            f.cpu.db, f.cpu.y, f.cpu.a = 0x2C, 0x53, 0xAB37
            f.cpu.c = f.cpu.v = f.cpu.i = True
            for a, v in ((0x10, 7), (0x1B, 1), (0xA0, 0x97), (0x048E, 0x97),
                         (0xAE, 0x39), (0x0E, 0xA6), (0x7EF3AD, 1),
                         (0x07F1, slot+1), (0x07F3, 1), (0x07F4, 0x97), (0x07F6, 0xBC),
                         (0x0C4A+slot, 7), (0x03EA+slot, 0xBC),
                         (0x0C04+slot, 0x90), (0x0C18+slot, 0x0E),
                         (0x0BFA+slot, 0x40), (0x0C0E+slot, 0x13),
                         (0x0DD6, 9), (0x0E26, 0xAF), (0x0D16, 0x90),
                         (0x0D36, 0x0E), (0x0D06, 0x40), (0x0D26, 0x13)):
                f.put(a, v)
            f.word(0x1982, 0x0118); f.word(0x1992, 0x0900)
            f.word(0x0400, 0x8000); f.word(0x068C, 0x8F00)
            f.word(0x0402, 0xAB00); f.word(0x0408, 5); f.word(0x7EF12E, 0x8AB5)
            f.writes.clear()
            return f

        def call(f, name='D6ChuGate97_Main', long=False):
            before = (f.cpu.y, f.cpu.db, f.cpu.dp, f.cpu.c, f.cpu.v, f.cpu.i, f.cpu.d)
            f.call(name, x=6, a=0x37, long_return=(long or name == 'D6ChuGate97_Main'))
            assert (f.cpu.y, f.cpu.db, f.cpu.dp) == before[:3]
            assert f.get(0x0E) == 0xA6
            if name == 'D6ChuGate97_Main':
                assert (f.cpu.c, f.cpu.v, f.cpu.i, f.cpu.d) == before[3:]
            return f

        for slot in (0, 1):
            f = call(fresh(slot))
            assert word(f, 0x0400) == 0x9000 and word(f, 0x7EF12E) == 0x9AB5
            assert f.get(0x039F+slot) == 1 and f.get(0x11) == 5
            assert word(f, 0x0468) == 0 and word(f, 0x068C) == 0x8F00
            allowed = {0, 1, 2, 3, 0x039F+slot, 0x0400, 0x0401, 0xF12E, 0xF12F,
                       0x0468, 0x0469, 0x068E, 0x068F, 0x0690, 0x0691, 0x11}
            assert all((a & 0xFFFF) in allowed or 0x100 <= (a & 0xFFFF) < 0x200
                       for a, _ in f.writes), f.writes
            f.word(0x068C, 0xCF00); f.put(0x11, 0); f.writes.clear(); call(f)
            assert f.get(0x11) == 0 and not [w for w in f.writes if w[0] == 0x7EF12E]
            cases.append('slot%d-earned-and-idempotent-without-paired0040' % slot); f.close()

        rejections = ((0x10, 9), (0x11, 5), (0x1B, 0), (0xA0, 0xD9), (0xA1, 1),
                      (0xAE, 0x17), (0xAF, 0x17), (0xEE, 1), (0x1982, 0x16),
                      (0x1992, 0x18), (0x0DD6, 0), (0x0E26, 0xF2), (0x0E36, 1),
                      (0x0F26, 1), (0x0D16, 0x91), (0x0D36, 0x0F),
                      (0x0D06, 0x41), (0x0D26, 0x14), (0x7EF3AD, 0),
                      (0x07F6, 0), (0x07F3, 0), (0x07F4, 0x87), (0x07F5, 1),
                      (0x07F7, 1), (0x07F1, 0), (0x07F1, 3), (0x07F1, 0xFF),
                      (0x0C4A, 1), (0x03EA, 0), (0x0C5E, 1), (0x039F, 1))
        for a, v in rejections:
            f = fresh(); f.put(a, v); f.writes.clear(); call(f)
            assert word(f, 0x7EF12E) == 0x8AB5 and not word(f, 0x0400) & 0x1000
            assert not [w for w in f.writes if w[0] == 0x7EF12E]
            cases.append('reject-%06x-%02x' % (a, v)); f.close()

        for axis, low, high, target in (('x', 0x0C04, 0x0C18, 0x0E90),
                                        ('y', 0x0BFA, 0x0C0E, 0x1340)):
            for delta in (-8, -7, 0, 22, 23):
                f = fresh(); v = target+delta; f.put(low, v); f.put(high, v >> 8); call(f)
                assert bool(word(f, 0x0400) & 0x1000) == (-7 <= delta <= 22)
                cases.append('contact-%s-%d' % (axis, delta)); f.close()
        f = fresh(); f.word(0x0400, 0xC000); f.word(0x068C, 0xCF00); f.put(0x07F1, 0)
        call(f)
        assert word(f, 0x0400) == 0x8000 and word(f, 0x068C) == 0xCF00
        assert word(f, 0x0468) == 1 and f.get(0x11) == 5
        cases.append('unearned-old-door-bit-animates-close'); f.close()
        f = fresh(); f.word(0x0400, 0x9000); f.put(0x07F1, 0); call(f)
        assert word(f, 0x0468) == 0 and f.get(0x11) == 5
        cases.append('earned-return-opens-without-live-chu'); f.close()

        f = fresh(body=disabled, symbols=off_labels)
        call(f, 'D9Actor_MainHandled', True)
        assert not f.cpu.c
        native_run(f, off_labels['CustomTag'], 0x2C7000)
        assert word(f, 0x0400) == 0x8000 and f.get(0x11) == 0
        cases.append('disabled-control-valid-contact-cannot-earn-or-open97'); f.close()
        for room in (0x87, 0xD7, 0xD9):
            for name in ('D9Actor_PrepDispatch', 'D9Actor_MainHandled'):
                a, b = fresh(), fresh(body=disabled, symbols=off_labels)
                for f in (a, b):
                    f.put(0xA0, room); f.put(0x048E, room); f.put(0xAE, 0x17)
                    f.word(0x0400, 0x1000); call(f, name, True)
                assert a.cpu.a == b.cpu.a and a.cpu.c == b.cpu.c
                assert all(0x100 <= n < 0x200 or x == y for n, (x, y) in
                           enumerate(zip(a.ram, b.ram)))
                cases.append('unchanged-AF-mode-%02x-%s' % (room, name)); a.close(); b.close()
        for db in (0, 9, 0x2C, 0x30, 0x80):
            f = fresh(); f.cpu.db = db; f.cpu.n = f.cpu.z = True
            call(f)
            assert f.cpu.n and f.cpu.z and word(f, 0x0400) == 0x9000
            cases.append('caller-ABI-mirrored-DBR-%02x' % db); f.close()

        # The existing shared predicate remains exact D7/D9, including NPC
        # consumers. Test all byte room IDs, both current and loaded contexts.
        for loaded in (False, True):
            for room in range(256):
                f = fresh(); f.put(0x048E if loaded else 0xA0, room)
                call(f, 'D6ChuActor_IsLoadedRoom' if loaded else 'D6ChuActor_IsRoom', True)
                assert f.cpu.c == (room in (0xD7, 0xD9)) and f.cpu.a == 0xAB37
                f.close()
            cases.append('shared-NPC-predicate-exact-256-rooms-' + str(loaded))
        for loaded, current, expected in ((0x97, 0x87, True), (0x87, 0x97, False)):
            f = fresh(); f.put(0x048E, loaded); f.put(0xA0, current)
            call(f, 'D6ChuGate97_IsLoadedTarget', True)
            assert f.cpu.c == expected and f.cpu.a == 0xAB37
            cases.append('prep-loaded-%02x-current-%02x' % (loaded, current)); f.close()
        for changed in (None, (0x0E36, 1), (0x0E26, 0xF2), (0x0F26, 1), (0xAE, 0x17)):
            f = fresh()
            if changed: f.put(*changed)
            call(f, 'D9Actor_PrepDispatch', True)
            assert f.get(0x0CAA+6) == (0x80 if changed is None else 0)
            f.word(0x0400, 0x1000)
            call(f, 'D9Actor_MainHandled', True)
            assert f.cpu.c == (changed is None)
            assert f.get(0x0D96) == int(changed is None)
            cases.append('AF-dispatch-exact-target-' + str(changed)); f.close()

        f = fresh()
        native_run(f, labels['CustomTag'], 0x2C7000)
        assert word(f, 0x0400) == 0x9000 and f.get(0x11) == 5
        assert f.cpu.x == 0 and f.cpu.y == 0x53 and f.cpu.db == 0x2C
        cases.append('actual-CustomTag-cross-bank-JSL-RTL'); f.close()

        # Native header tag stores precede ResetSprites in the transition:
        # $028A5B JSL Underworld_LoadRoom, then $028A77 JSL ResetSprites.
        # Execute the real stores before AF prep with a stale departing A0.
        assert reference[pc(0x028A5B)] == 0x22 and reference[pc(0x028A77)] == 0x22
        for loaded, current, tag, expect in ((0x97, 0x87, 0x39, True),
                                             (0x87, 0x97, 0x17, False),
                                             (0x97, 0x87, 0x17, False)):
            f = fresh(); f.rom = reference
            f.put(0xA0, current); f.put(0x048E, loaded); f.put(0xAE, 0x17); f.put(0xAF, 0x39)
            f.put(0x0D, 0); f.put(0x0E, 0x10); f.put(0x0F, 0x7E)
            f.put(0x1001, tag); f.put(0x1002, 0); f.cpu.y = 0
            native_run(f, 0x01B655, 0x01B65F)
            assert f.get(0xAE) == tag and f.get(0xAF) == 0
            f.rom = compiled; f.put(0x0E, 0xA6)
            call(f, 'D9Actor_PrepDispatch', True)
            assert f.get(0x0CAA+6) == (0x80 if expect else 0)
            cases.append('native-tag-stores-before-loaded-AF-prep-%02x-%02x' % (loaded, tag)); f.close()

        # Execute exact native door drawing against the frozen reference.
        f = NativeFixture(lib, reference, {})
        f.cpu.db = 0; f.cpu.mf = f.cpu.xf = False; f.cpu.y = 0x121C
        for a, v in ((2, 0x0C), (4, 0x36), (0x0A, 0x36), (0x0460, 2),
                     (0x0468, 1), (0x068C, 0x0F00)):
            f.word(a, v)
        for a, v in ((0xBF, 0x7E2000), (0xCB, 0x7E2080), (0xD7, 0x7E2100),
                     (0xDA, 0x7E2180), (0xDD, 0x7E2200)):
            for n in range(3): f.put(a+n, v >> (8*n))
        native_run(f, 0x01A90F)
        assert word(f, 0x1982) == 0x0118 and word(f, 0x1992) == 0x0900
        assert word(f, 0x19A2) == 0x121C and word(f, 0x19B2) == 0x0D1C
        assert word(f, 0x0400) == 0
        cases.append('native-type36-north18-paired-south00')
        for closing, initial, expected in ((0, 0x8F00, 0xCF00), (1, 0xCF00, 0x8F00)):
            f.word(0x068C, initial); f.word(0x0468, closing); f.word(0x0690, 7)
            f.calls.clear(); native_run(f, 0x01D38F, long_return=True)
            assert word(f, 0x068C) == expected
            assert (0x01D311, 2) in f.calls and (0x01D51C, 2) in f.calls
            assert len(f.calls) == 3, f.calls
            cases.append('native-animation-only-door1-' + str(closing))
        f.close()

        f = Fixture(lib, reference, {}); f.cpu.db = 0
        f.word(0xA0, 0x97); f.word(0x0400, 0x9000)
        f.word(0x0402, 0xAB00); f.word(0x0408, 5)
        native_run(f, 0x02B947)
        assert word(f, 0x7EF12E) == 0x9AB5
        f.word(0x0400, 0); f.word(0x0402, 0); f.word(0x0408, 0)
        f.cpu.mf = f.cpu.xf = False
        native_run(f, 0x01B6D1, 0x01B6FD)
        assert (word(f, 0x0400), word(f, 0x0402), word(f, 0x0408), word(f, 0x068C)) == (
            0x9000, 0xAB00, 5, 0x9F00)
        cases.append('native-room-state-save-load-preserves-earned-chest-and-low-flags'); f.close()
        # Startup/reentry combines native saved1000 load + native door draw
        # with the new handler, then the real door1-only animation decision.
        f = fresh(); f.rom = reference; f.cpu.db = 0
        f.word(0x7EF12E, 0x9AB5); f.cpu.mf = f.cpu.xf = False
        native_run(f, 0x01B6D1, 0x01B6FD)
        for a, v in ((2, 0x0C), (4, 0x36), (0x0A, 0x36), (0x0460, 2), (0x0468, 1)):
            f.word(a, v)
        for a, v in ((0xBF, 0x7E2000), (0xCB, 0x7E2080), (0xD7, 0x7E2100),
                     (0xDA, 0x7E2180), (0xDD, 0x7E2200)):
            for n in range(3): f.put(a+n, v >> (8*n))
        f.cpu.y = 0x121C; native_run(f, 0x01A90F)
        assert word(f, 0x1982) == 0x0118 and word(f, 0x1992) == 0x0900
        f.rom = compiled; f.cpu.mf = f.cpu.xf = True
        f.cpu.x &= 0xFF; f.cpu.y &= 0xFF  # native caller SEP30 truncation
        f.put(0x0E, 0xA6); f.put(0x07F1, 0); call(f)
        assert f.get(0x11) == 5 and word(f, 0x0468) == 0
        n = NativeFixture(lib, reference, {}); n.ram[:] = f.ram; n.cpu.db = 0
        n.word(0x0690, 7); native_run(n, 0x01D38F, long_return=True)
        assert word(n, 0x068C) == 0xDF00 and word(n, 0x0400) == 0x9000
        f.ram[:] = n.ram; f.put(0x11, 0); call(f)
        assert f.get(0x11) == 0 and not word(f, 0x068C) & 0x0040
        cases.append('native-saved1000-startup-draw-single4000-open-idempotent')
        f.close(); n.close()
        result = {'passed': True, 'case_count': len(cases), 'cases': cases,
                  'reference_sha256': REFERENCE_SHA,
                  'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'Dungeons/d6_chu_gate_97.asm', ROOT/'Dungeons/custom_tag.asm', ROOT/'Dungeons/d9_key_gate.asm', ROOT/'Dungeons/d6_cart_circuit.asm', ROOT/'Tests/test_d6_chu_gate_97_compiled.py')},
                  'synthetic_enabled_span_bytes': labels['FixtureEnd']-0x2C9000,
                  'synthetic_disabled_span_bytes': off_labels['FixtureEnd']-0x2C9000,
                  'added_bank2C_bytes': labels['FixtureEnd']-off_labels['FixtureEnd'],
                  'added_bank2B_bytes': labels['FixtureGateEnd']-0x2BBE22,
                  'module_synthetic_snes_range': [hex(labels['D6ChuGate97_CodeStart']), hex(labels['D6ChuGate97_CodeEnd'])],
                  'door_stream': '63006036ffff', 'live_shutter_mask': '4000',
                  'conditional_earned_mask': '1000',
                  'scope': 'Compiled synthetic CPU plus actual reference native door/state decisions. Animation draw/DMA/collision calls stubbed. No native input, collision, PPU, route or saved-file proof.'}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
