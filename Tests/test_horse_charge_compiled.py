#!/usr/bin/env python3
"""Compile Masks/horse_charge.asm and run it on the Lakesnes 65816 core.

Synthetic FF image; no game ROM, PPU or controller proof. The three vanilla
bank-$06 services are stubs: Sprite_SetupHitbox_long ($0683EA) gives each
sprite a 16x16 box at its XY, CheckIfHitBoxesOverlap_long ($0683E6) runs the
vanilla overlap test on DP $00-$0B, and $06ED25 records the damage call and
marks the sprite as flashing ($0EF0). Everything else executes real bytes.
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
SETUP, OVERLAP, DAMAGE = 0x0683EA, 0x0683E6, 0x06ED25


def assemble(folder):
    folder.mkdir()
    (folder/'horse_charge.asm').write_bytes((ROOT/'Masks/horse_charge.asm').read_bytes())
    asm = folder/'fixture.asm'
    asm.write_text('lorom\norg $3A8000\n!HorsePark_SpriteId = $2D\nincsrc "horse_charge.asm"\n')
    image = folder/'fixture.sfc'
    image.write_bytes(b'\xff' * 0x200000)
    result = subprocess.run(['asar', '--no-title-check', '--fix-checksum=off',
                             '--symbols=wla', str(asm), str(image)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    labels = {m[3]: int(m[1]+m[2], 16) for m in re.finditer(
        r'(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$', image.with_suffix('.sym').read_text())}
    return image.read_bytes(), labels


class HorseFixture(Fixture):
    def __init__(self, lib, rom, labels):
        super().__init__(lib, rom, labels)
        self.stubs = {SETUP: 'setup', OVERLAP: 'overlap', DAMAGE: 'damage'}
        self.cpu.db = 0x00
        self.hits = []
        self.word(0x22, 100); self.word(0x20, 100)    # Link X/Y

    def enemy(self, slot, x, y, sid=0x08, state=9, harmless=False):
        self.put(0xDD0+slot, state); self.put(0xE20+slot, sid)
        self.put(0xE40+slot, 0x80 if harmless else 0x03)
        self.put(0xD10+slot, x & 255); self.put(0xD30+slot, x >> 8)
        self.put(0xD00+slot, y & 255); self.put(0xD20+slot, y >> 8)

    def stub(self, name):
        x = self.cpu.x & 255
        if name == 'setup':
            self.put(0x04, self.get(0xD10+x)); self.put(0x0A, self.get(0xD30+x))
            self.put(0x05, self.get(0xD00+x)); self.put(0x0B, self.get(0xD20+x))
            self.put(0x06, 16); self.put(0x07, 16)
        elif name == 'overlap':
            ax = self.get(0x00) | self.get(0x08) << 8; ay = self.get(0x01) | self.get(0x09) << 8
            bx = self.get(0x04) | self.get(0x0A) << 8; by = self.get(0x05) | self.get(0x0B) << 8
            aw, ah, bw, bh = (self.get(a) for a in (0x02, 0x03, 0x06, 0x07))
            sx = lambda v: v - 0x10000 if v & 0x8000 else v
            ax, ay, bx, by = sx(ax), sx(ay), sx(bx), sx(by)
            self.cpu.c = ax < bx+bw and bx < ax+aw and ay < by+bh and by < ay+ah
        elif name == 'damage':
            self.hits.append(dict(slot=x, cls=self.cpu.a & 255,
                                  ry=self.get(0xF30+x), rx=self.get(0xF40+x)))
            self.put(0xEF0+x, 0x80)

    def run(self, name, x=0x33, y=0x44, a=0x55):
        c = self.cpu; c.mf = c.xf = True; c.x, c.y = x, y; c.a = (c.a & 0xFF00) | a
        entry = self.addr(name); assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 65535
        sp = c.sp; self.put(sp, c.k); self.put(sp-1, 0x6F); self.put(sp-2, 0xFF); c.sp -= 3
        for count in range(50000):
            address = c.k << 16 | c.pc
            if address == (entry & 0xFF0000) | 0x7000:
                assert c.sp == sp and not self.bad_writes, (name, c.sp, self.bad_writes)
                assert c.db == 0 and c.mf and c.xf, (name, 'ABI')
                return count
            if address in self.stubs: self.calls.append(self.stubs[address]); self.stub(self.stubs[address])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name, 'instruction bound', hex(c.k << 16 | c.pc)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lakesnes', type=Path, required=True)
    ap.add_argument('--output', type=Path)
    a = ap.parse_args(); cases = []
    with tempfile.TemporaryDirectory(prefix='horse-charge-cpu-') as tmp:
        d = Path(tmp); library = d/'cpu.dylib'
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', str(a.lakesnes/'snes/cpu.c'),
                        str(a.lakesnes/'snes/statehandler.c'), '-o', str(library)], check=True)
        lib = C.CDLL(str(library)); lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]; lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        rom, labels = assemble(d/'build')

        def case(name, fn):
            f = HorseFixture(lib, rom, labels)
            try: fn(f); cases.append(name)
            finally: f.close()

        # --- Crowd check ---
        def crowd(n, extra=None):
            def fn(f):
                for s in range(n): f.enemy(s, 40+s*16, 40)
                if extra: extra(f)
                f.run('HorseCrowd_Check')
                c = f.cpu
                assert (c.x & 255, c.y & 255, c.a & 255) == (0x33, 0x44, 0x55), 'A/X/Y preserved'
                return c.c
            return fn
        def four_ok(f): assert crowd(4)(f) is False
        def five_refuse(f): assert crowd(5)(f) is True
        def ignored(f):
            def extra(f):
                f.enemy(10, 0, 0, harmless=True)             # NPC-like
                f.enemy(11, 0, 0, sid=0x2D, harmless=False)  # Epona herself
                f.enemy(12, 0, 0, sid=0xD9)                  # pickup
                f.enemy(13, 0, 0, state=6)                   # dying
            assert crowd(4, extra)(f) is False
        def at_limit_counts_stunned(f):
            assert crowd(4, lambda f: f.enemy(9, 0, 0, state=0x0B))(f) is True
        case('crowd_4_enemies_allows', four_ok)
        case('crowd_5_enemies_refuses', five_refuse)
        case('crowd_ignores_npc_epona_pickup_dying', ignored)
        case('crowd_counts_stunned_enemy', at_limit_counts_stunned)

        # --- Charge hit ---
        def charge(facing, ex, ey, sid=0x08, pad=0x01, prep=None):
            f_hits = {}
            def fn(f):
                f.put(0xF0, pad); f.put(0x2F, facing)
                f.enemy(5, ex, ey, sid=sid)
                if prep: prep(f)
                f.run('HorseCharge_Tick_Long')
                f_hits['hits'] = f.hits
            return fn, f_hits
        def expect(facing, ex, ey, want, **kw):
            fn, out = charge(facing, ex, ey, **kw)
            def check(f):
                fn(f); h = out['hits']
                if want is None: assert h == [], h
                else: assert h == [dict(slot=5, cls=1, **want)], h
            return check
        case('right_front_hit_knocks_right', expect(6, 122, 96, dict(ry=0x00, rx=0x40)))
        case('left_front_hit_knocks_left', expect(4, 80, 96, dict(ry=0x00, rx=0xC0)))
        case('up_front_hit_knocks_up', expect(0, 100, 74, dict(ry=0xC0, rx=0x00)))
        case('down_front_hit_knocks_down', expect(2, 100, 112, dict(ry=0x40, rx=0x00)))
        case('behind_enemy_not_hit', expect(6, 60, 96, None))
        case('standing_still_no_hit', expect(6, 122, 96, None, pad=0x00))
        case('armos_immune', expect(6, 122, 96, None, sid=0x51))
        case('chain_chomp_immune', expect(6, 122, 96, None, sid=0xCA))
        case('boss_property_immune', expect(6, 122, 96, None, prep=lambda f: f.put(0xB6B+5, 0x02)))
        case('impervious_immune', expect(6, 122, 96, None, prep=lambda f: f.put(0xE60+5, 0x40)))
        case('flashing_not_rehit', expect(6, 122, 96, None, prep=lambda f: f.put(0xEF0+5, 0x80)))
        case('airborne_not_hit', expect(6, 122, 96, None, prep=lambda f: f.put(0xF70+5, 0x18)))
        case('harmless_npc_not_hit', expect(6, 122, 96, None,
                                            prep=lambda f: f.put(0xE40+5, 0x80)))

        def once_per_flash(f):
            f.put(0xF0, 0x01); f.put(0x2F, 6); f.enemy(5, 122, 96)
            f.run('HorseCharge_Tick_Long'); f.run('HorseCharge_Tick_Long')
            assert len(f.hits) == 1, f.hits
        case('one_hit_per_damage_flash', once_per_flash)

    result = {'status': 'PASS', 'cases': cases, 'count': len(cases)}
    text = json.dumps(result, indent=2)
    if a.output: a.output.write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
