#!/usr/bin/env python3
"""Execute the actual address-parameterized binding core on the existing CPU.

Synthetic image and TEST-ONLY addresses. No production grant, live dispatch,
PPU, game Save or controller proof. The shared D4 fixture is unchanged at 025.
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
FIELDS = ('SavedVersion', 'SavedY', 'SavedX', 'Cursor', 'Logical', 'Action', 'Button')
# Synthetic fixture storage ONLY: never export these addresses to game source.
ADDR = {name: 0x7E6000 + i for i, name in enumerate(FIELDS)}


def assemble(folder, source):
    folder.mkdir()
    (folder / 'item_bindings.asm').write_text(source)
    asm = folder / 'fixture.asm'
    asm.write_text('lorom\n' + '\n'.join(
        f'ItemBinding{name} = ${addr:06X}' for name, addr in ADDR.items()) +
        '\norg $208000\nnamespace Oracle\nincsrc "item_bindings.asm"\nnamespace off\n')
    image = folder / 'fixture.sfc'
    image.write_bytes(b'\xff' * 0x110000)
    p = subprocess.run(['asar', '--no-title-check', '--fix-checksum=off',
                        '--symbols=wla', str(asm), str(image)], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    labels = {m[3]: int(m[1] + m[2], 16) for m in re.finditer(
        r'(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$', image.with_suffix('.sym').read_text())}
    return image.read_bytes(), labels


class BindingFixture(Fixture):
    def __init__(self, lib, rom, labels):
        super().__init__(lib, rom, labels)
        self.stubs = {}
        self.put(0x7EF340, 1); self.put(0x7EF341, 1)
        self.field('SavedVersion', 1); self.field('SavedY', 1); self.field('SavedX', 2)

    def field(self, name, value=None):
        if value is not None:
            self.put(ADDR[name], value)
        return self.get(ADDR[name])

    def run(self, name, a=0, m8=True, x8=True, carry=False):
        c = self.cpu
        c.mf = m8; c.xf = x8; c.a = 0xAB00 | a
        c.x = 0x56 if x8 else 0x3456; c.y = 0x78 if x8 else 0x5678
        c.db = 0x41; c.dp = 0; c.c = carry; c.v = True
        x, y, sp = c.x, c.y, c.sp
        entry = self.addr('ItemBindings_' + name)
        assert entry is not None, name
        c.k = entry >> 16; c.pc = entry & 65535
        self.put(sp, c.k); self.put(sp - 1, 0x6F); self.put(sp - 2, 0xFF); c.sp -= 3
        before = bytes(self.ram)
        for _ in range(500):
            if (c.k << 16 | c.pc) == ((entry & 0xFF0000) | 0x7000):
                assert (c.x, c.y, c.sp, c.db, c.dp, c.mf, c.xf, c.v) == (
                    x, y, sp, 0x41, 0, m8, x8, True), (name, 'ABI')
                assert c.a & 0xFF00 == 0xAB00, (name, 'A high byte')
                assert not self.bad_writes, self.bad_writes
                allowed = set(range(0x100, 0x200)) | {address - 0x7E0000 for address in ADDR.values()}
                changed = {i for i, (old, new) in enumerate(zip(before, self.ram)) if old != new}
                assert changed <= allowed, (name, 'foreign state changed', changed - allowed)
                return c.a & 255
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name, 'instruction bound', hex(c.k << 16 | c.pc)))


def exercise(lib, rom, labels):
    cases = []

    def check(name, fn):
        f = BindingFixture(lib, rom, labels)
        try:
            fn(f)
            cases.append(name)
        finally:
            f.close()

    for schema in (0, 0xFF, 0xA5):
        for prior in (0, 1, 2, 0x1D):
            def migrate(f, schema=schema, prior=prior):
                f.field('SavedVersion', schema); f.field('SavedX', 2)
                f.put(0x202, prior)
                for k in ('Logical', 'Action', 'Button'): f.field(k, 0xFF)
                f.run('Load')
                expected = prior if prior in (1, 2) else 1
                assert [f.field(k) for k in FIELDS] == [1, expected, 0, expected, 0, 0, 0]
                assert f.get(0x202) == prior
            check(f'migration-{schema}-{prior}', migrate)

    for bow, boom, expected in ((0, 0, 0), (0, 2, 2), (4, 0, 1), (5, 3, 0)):
        def fallback(f, bow=bow, boom=boom, expected=expected):
            f.put(0x7EF340, bow); f.put(0x7EF341, boom)
            f.field('SavedVersion', 0); f.run('Load')
            assert f.field('SavedY') == expected and f.field('Cursor') == expected
            assert f.field('SavedX') == 0
        check(f'fallback-and-invalid-inventory-{bow}-{boom}', fallback)

    def current(f):
        f.field('SavedY', 2); f.field('SavedX', 1); f.run('Load')
        assert (f.field('SavedY'), f.field('SavedX'), f.field('Cursor')) == (2, 1, 2)
        f.put(0x7EF340, 0); f.run('Load')
        assert (f.field('SavedY'), f.field('SavedX')) == (2, 0)
    check('current-schema-revalidates-without-grants', current)

    def independent(f):
        f.run('Load'); f.run('SetCursor', 2)
        assert f.cpu.c and (f.field('SavedY'), f.field('SavedX')) == (1, 2)
        f.run('AssignY'); assert f.cpu.c and f.field('SavedY') == 2
        f.run('SetCursor', 1); f.run('AssignX')
        assert f.cpu.c and (f.field('SavedY'), f.field('SavedX')) == (2, 1)
        f.run('AssignY'); assert f.field('SavedY') == f.field('SavedX') == 1
    check('cursor-independent-and-duplicate-binding', independent)

    for invalid in (0, 3, 6, 0x1D, 0xFF):
        def refusal(f, invalid=invalid):
            f.field('Cursor', 2); f.run('SetCursor', invalid)
            assert not f.cpu.c and f.field('Cursor') == 2
            f.field('Cursor', invalid)
            f.run('AssignX'); assert not f.cpu.c and f.field('SavedX') == 2
            f.run('AssignY'); assert not f.cpu.c and f.field('SavedY') == 1
        check(f'unsupported-binding-refusal-{invalid}', refusal)

    for button, logical, action in ((1, 1, 3), (2, 2, 2)):
        def latch(f, button=button, logical=logical, action=action):
            f.put(0xF4 if button == 1 else 0xF6, 0x40)
            f.run('TryBegin', 1)
            assert f.cpu.c and [f.field(k) for k in ('Logical','Action','Button')] == [logical,action,button]
            f.put(0xF4, 0x40); f.put(0xF6, 0x40)
            f.run('TryBegin', 1); assert not f.cpu.c and f.field('Logical') == logical
            f.run('SetCursor', 2 if logical == 1 else 1); f.run('AssignX'); f.run('AssignY')
            assert f.run('GetLogical') == logical
            f.put(0xF4, 0); f.put(0xF6, 0); f.put(0xF0, 0); f.put(0xF2, 0)
            assert f.run('GetHeld') == 0 and f.field('Button') == button
            f.run('EndAction')
            assert all(f.field(k) == 0 for k in ('Logical', 'Action', 'Button'))
            assert f.run('GetLogical') == f.field('SavedY')
        check(f'latched-identity-completion-button-{button}', latch)

    def priority(f):
        f.put(0xF4, 0x40); f.put(0xF6, 0x40); f.run('TryBegin', 1)
        assert f.cpu.c and f.field('Button') == 1 and f.field('Logical') == 1
        f.run('EndAction'); f.field('SavedY', 0); f.run('TryBegin', 1)
        assert not f.cpu.c and f.field('Button') == 0
    check('simultaneous-Y-priority-and-no-X-fallback', priority)

    for permit in (0, 2, 0xFF):
        def denied(f, permit=permit):
            f.put(0xF4, 0x40); f.put(0xF6, 0x40); f.run('TryBegin', permit)
            assert not f.cpu.c and f.field('Button') == 0
        check(f'dispatcher-denies-start-{permit}', denied)

    def no_press(f):
        f.run('TryBegin', 1); assert not f.cpu.c and f.field('Button') == 0
    check('no-press-no-action', no_press)

    for button in (0, 1, 2):
        for y, x in ((0,0), (0x40,0), (0,0x40), (0x40,0x40)):
            def inputs(f, button=button, y=y, x=x):
                f.field('Button', button)
                # Preserve A, B, R, Start and direction bits while querying.
                f.put(0xF0, y | 0x9F); f.put(0xF4, y | 0xBF)
                f.put(0xF2, x | 0xB0); f.put(0xF6, x | 0xB0)
                expected = y if button == 1 else x if button == 2 else 0
                assert f.run('GetHeld') == expected and f.run('GetNew') == expected
            check(f'scoped-input-{button}-{y}-{x}', inputs)

    def reload(f):
        f.run('SetCursor', 2); f.run('AssignY')
        f.run('SetCursor', 1); f.run('AssignX')
        saved = [f.field(k) for k in FIELDS[:3]]
        g = BindingFixture(lib, rom, labels)
        try:
            for k, v in zip(FIELDS[:3], saved): g.field(k, v)
            g.run('Load')
            assert [g.field(k) for k in FIELDS[:3]] == [1,2,1]
            assert all(g.field(k) == 0 for k in ('Logical','Action','Button'))
        finally: g.close()
    check('saved-record-copied-to-fresh-CPU-not-native-save', reload)

    routines = ('Load','SetCursor','AssignX','AssignY','TryBegin','EndAction',
                'GetLogical','GetHeld','GetNew')
    for m8 in (False, True):
        for x8 in (False, True):
            for routine in routines:
                def abi(f, routine=routine, m8=m8, x8=x8):
                    f.field('Cursor', 1); f.put(0xF6, 0x40)
                    f.run(routine, 1, m8=m8, x8=x8, carry=True)
                check(f'ABI-{routine}-M{8 if m8 else 16}-X{8 if x8 else 16}', abi)
    return cases


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lakesnes', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    source = (ROOT/'Items/item_bindings.asm').read_text()
    with tempfile.TemporaryDirectory(prefix='item-bindings-cpu-') as tmp:
        folder = Path(tmp); library = folder/'cpu.dylib'
        subprocess.run(['cc','-shared','-fPIC','-O2',str(args.lakesnes/'snes/cpu.c'),
                        str(args.lakesnes/'snes/statehandler.c'),'-o',str(library)], check=True)
        lib = C.CDLL(str(library)); lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]; lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        rom, labels = assemble(folder/'candidate', source)
        cases = exercise(lib, rom, labels)
        controls = []
        # Prove tests detect wrong action, broken origin and false migration.
        mutations = {
            'bow-action-wrong': source.replace('  db $03, $02, $0E', '  db $02, $02, $0E'),
            'X-origin-marked-Y': source.replace('LDA.b #$02 : BRA .commit', 'LDA.b #$01 : BRA .commit'),
            'old-save-X-not-cleared': source.replace('LDA.b #$00 : STA.l ItemBindingSavedX\n  LDA.l $7E0202', 'LDA.b #$02 : STA.l ItemBindingSavedX\n  LDA.l $7E0202'),
        }
        for name, bad in mutations.items():
            assert bad != source
            badrom, badlabels = assemble(folder/name, bad)
            try:
                exercise(lib, badrom, badlabels)
            except AssertionError:
                controls.append(name)
            else:
                raise AssertionError(('mutation escaped', name))
        result = {'status':'PASS', 'source_base':'025cf964555855c3c7d49278b4559f4d0ef4f311',
                  'module_sha256': hashlib.sha256(source.encode()).hexdigest(),
                  'cases':cases, 'passed':len(cases), 'mutation_controls_rejected':controls,
                  'limits':['Synthetic addresses only; no production allocation',
                            'No live hooks, vanilla dispatch, native gameplay or actual Save/reload']}
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({'passed':len(cases),'mutation_controls_rejected':len(controls)}))


if __name__ == '__main__':
    main()
