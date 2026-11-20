#!/usr/bin/env python3
"""Compile the Ranch Girl milk sale and run it on the
Lakesnes 65816 core.

Assembles Sprites/NPCs/ranch_girl.asm and Sprites/NPCs/ranch_milk.asm into a
synthetic FF image. Sprite_ShowMessageUnconditional is a stub that records the
message ID and sets the module to $0E like the vanilla routine; every other
instruction is the real assembled code. No game ROM, PPU or controller proof.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import subprocess
import tempfile
from d4_compiled_fight_check import Cpu, Fixture

ROOT = Path(__file__).resolve().parents[1]
SHOW = 0x05E219                     # Sprite_ShowMessageUnconditional
RUPEES, BOTTLES, CHOICE = 0x7EF360, 0x7EF35C, 0x1CE8
MISC_D, FLUTE, SQ2, MODULE = 0x0E90, 0x7EF34C, 0x7EF3D8, 0x10

FIXTURE = """lorom
!SideQuest2_EponaSong = $02
!MapIcon_TailPond = $05
SprMiscC = $0DE0
SprTimerA = $0DF0
SprMiscD = $0E90
SideQuestProg2 = $7EF3D8
MapIcon = $7EF3C7
Link_ReceiveItem = $0791B3
SpriteDraw_RaceGameLady = $0DFE00
Sprite_ShowMessageUnconditional = $05E219
macro ShowUnconditionalMessage(message_id)
  LDY.b #(<message_id>)>>8
  LDA.b #<message_id>
  JSL Sprite_ShowMessageUnconditional
endmacro
org $328000
incsrc "ranch_girl.asm"
org $308000
incsrc "ranch_milk.asm"
"""


def assemble(folder):
    folder.mkdir()
    for name in ('ranch_girl.asm', 'ranch_milk.asm'):
        (folder/name).write_bytes((ROOT/'Sprites/NPCs'/name).read_bytes())
    asm = folder/'fixture.asm'
    asm.write_text(FIXTURE)
    image = folder/'fixture.sfc'
    image.write_bytes(b'\xff' * 0x200000)
    result = subprocess.run(['asar', '--no-title-check', '--fix-checksum=off',
                             '--symbols=wla', str(asm), str(image)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    labels = {m[3]: int(m[1]+m[2], 16) for m in re.finditer(
        r'(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$', image.with_suffix('.sym').read_text())}
    return image.read_bytes(), labels


class MilkFixture(Fixture):
    def __init__(self, lib, rom, labels):
        super().__init__(lib, rom, labels)
        self.stubs = {SHOW: 'show'}
        self.cpu.db = 0x05            # ChickenLady runs with DBR = $05
        self.messages = []
        self.put(MODULE, 0x09)
        self.put(FLUTE, 0x01)         # has the Ocarina
        self.put(SQ2, 0x03)           # revealed + knows Epona's Song
        self.rupees(50)
        self.bottles(0x02, 0x00, 0x00, 0x00)

    def rupees(self, n=None):
        if n is not None:
            self.put(RUPEES, n & 255); self.put(RUPEES+1, n >> 8)
        return self.get(RUPEES) | self.get(RUPEES+1) << 8

    def bottles(self, *values):
        if values:
            for i, v in enumerate(values): self.put(BOTTLES+i, v)
        return [self.get(BOTTLES+i) for i in range(4)]

    def stub(self, name):
        c = self.cpu
        self.messages.append((c.y & 255) << 8 | (c.a & 255))
        self.put(MODULE, 0x0E)

    def run(self, name, x=0x05):
        c = self.cpu; c.mf = c.xf = True; c.x = x; c.y = 0
        entry = self.addr(name); assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 65535
        sp = c.sp; self.put(sp, c.k); self.put(sp-1, 0x6F); self.put(sp-2, 0xFF); c.sp -= 3
        for count in range(20000):
            address = c.k << 16 | c.pc
            if address == (entry & 0xFF0000) | 0x7000:
                assert c.sp == sp and not self.bad_writes, (name, c.sp, self.bad_writes)
                assert c.db == 0x05 and c.mf and c.xf, (name, 'ABI')
                assert c.x & 255 == x, (name, 'X preserved')
                return count
            if address in self.stubs:
                self.calls.append(self.stubs[address]); self.stub(self.stubs[address])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name, 'instruction bound', hex(c.k << 16 | c.pc)))

    def visit(self, choice):
        """Powder reveal on a later visit, then answer the offer."""
        self.run('RanchGirl_Message')
        assert self.messages == [0x187], self.messages
        assert self.get(MISC_D+5) == 2
        self.run('RanchGirl_TeachSong')           # box still open: no sale yet
        assert self.messages == [0x187] and self.get(MISC_D+5) == 2
        self.put(MODULE, 0x09); self.put(CHOICE, choice)
        self.run('RanchGirl_TeachSong')           # box closed: sale resolves
        assert self.get(MISC_D+5) == 0
        return self.messages[1:]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lakesnes', type=Path, required=True)
    ap.add_argument('--output', type=Path)
    a = ap.parse_args(); cases = []
    with tempfile.TemporaryDirectory(prefix='ranch-milk-cpu-') as tmp:
        d = Path(tmp); library = d/'cpu.dylib'
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', str(a.lakesnes/'snes/cpu.c'),
                        str(a.lakesnes/'snes/statehandler.c'), '-o', str(library)], check=True)
        lib = C.CDLL(str(library)); lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]; lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        rom, labels = assemble(d/'build')

        def case(name, fn):
            f = MilkFixture(lib, rom, labels)
            try: fn(f); cases.append(name)
            finally: f.close()

        def buy(f):
            assert f.visit(0) == [0x188]
            assert f.rupees() == 20 and f.bottles() == [0x0A, 0, 0, 0]
        def buy_fills_first_empty(f):
            f.bottles(0x03, 0x0A, 0x02, 0x02)
            assert f.visit(0) == [0x188]
            assert f.bottles() == [0x03, 0x0A, 0x0A, 0x02] and f.rupees() == 20
        def exact_30(f):
            f.rupees(30); assert f.visit(0) == [0x188]; assert f.rupees() == 0
        def too_poor(f):
            f.rupees(29); assert f.visit(0) == [0x189]
            assert f.rupees() == 29 and f.bottles() == [0x02, 0, 0, 0]
        def no_empty_bottle(f):
            f.bottles(0x0A, 0x03, 0x00, 0x04); assert f.visit(0) == [0x033]
            assert f.rupees() == 50 and f.bottles() == [0x0A, 0x03, 0x00, 0x04]
        def reject(f):
            assert f.visit(1) == [0x18B]
            assert f.rupees() == 50 and f.bottles() == [0x02, 0, 0, 0]
        def first_visit_unchanged(f):
            f.put(FLUTE, 0x00); f.put(SQ2, 0x00)
            f.run('RanchGirl_Message')
            assert f.messages == [0x1BE] and f.get(MISC_D+5) == 1
        def big_rupees(f):
            f.rupees(0x01F4); assert f.visit(0) == [0x188]; assert f.rupees() == 0x01D6
        case('buy_milk_30_rupees', buy)
        case('buy_fills_first_empty_bottle', buy_fills_first_empty)
        case('exactly_30_rupees', exact_30)
        case('29_rupees_not_enough', too_poor)
        case('no_empty_bottle', no_empty_bottle)
        case('reject_keeps_rupees', reject)
        case('first_visit_still_gives_ocarina', first_visit_unchanged)
        case('16bit_rupee_subtract', big_rupees)

    result = {'status': 'PASS', 'cases': cases, 'count': len(cases)}
    text = json.dumps(result, indent=2)
    if a.output: a.output.write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
