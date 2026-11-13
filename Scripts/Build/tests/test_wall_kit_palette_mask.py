"""Execute the real kit converter; its only hardware effect is $2118 writes.

This focused model validates plane expansion and caller/stack/scratch contracts.
Native NMI timing, room traversal and save/reopen remain separate T3 evidence.
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_lw_sprite_resource_phase import Machine, routine

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'Scripts/Generate'))
import gen_wall_profiles as profiles
import sheet_codec


class Converter(Machine):
    def __init__(self, rom, raw, row=0x17, slot=1, indoor=1):
        super().__init__(rom, state=2, hour=12)
        self.pc, self.p, self.d, self.db = 0x44E200, 0x10, 0, 0
        self.a, self.x, self.y = 0xABCD, 0x72, 63
        self.stack = [0x5A, 0xC3]
        self.push(0xE2C6, 2)
        self.mem = {0x7E001B: indoor, 0x7E0AA2: row, 0x7E000F: slot,
                    0x7E0000: 0, 0x7E0001: 0x72, 0x7E0002: 0x7E}
        self.mem.update({0x7E7200 + i: v for i, v in enumerate(raw)})
        self.stops = (0x00E63C, 0x00E5AF, 0x00E6B6)
        self.words = []
        self.writes = set()

    def value(self, addr, size):
        return sum(self.read(addr + i) << (8 * i) for i in range(size))

    def write(self, addr, value, size):
        if addr == 0x2118:
            assert size == 2
            self.words.append(value & 0xFFFF)
            return
        for i in range(size):
            a = addr + i
            if a < 0x2000: a |= 0x7E0000
            self.mem[a] = value >> (8 * i) & 255
            self.writes.add(a)

    def run(self):
        for _ in range(40000):
            if self.pc in self.stops: return self
            op = self.fetch()
            m = 1 if self.p & 0x20 else 2
            ix = 1 if self.p & 0x10 else 2
            imask = (1 << (ix*8))-1
            if op == 0xAF: self.load_a(self.value(self.fetch(3), m), m)
            elif op == 0xBF: self.load_a(self.value(self.fetch(3) + self.x, m), m)
            elif op == 0xA6: self.x = self.read(self.fetch()); self.nz(self.x, 1)
            elif op in (0xA2, 0xA0):
                reg = 'x' if op == 0xA2 else 'y'; setattr(self, reg, self.fetch(ix)); self.nz(getattr(self,reg),ix)
            elif op == 0xE0:
                v = self.fetch(ix); self.p = self.p & ~1 | int(self.x >= v); self.nz(self.x - v, ix)
            elif op == 0xC9:
                v = self.fetch(m); self.p = self.p & ~1 | int(self.a >= v); self.nz(self.a - v, m)
            elif op in (0x29, 0x49):
                v = self.fetch(m); self.load_a(self.a & v if op == 0x29 else self.a ^ v, m)
            elif op in (0x18, 0x38): self.p = self.p & ~1 | int(op == 0x38)
            elif op == 0xE9:
                v = self.fetch(m); n = self.a - v - (not self.p & 1)
                self.p = self.p & ~1 | int(n >= 0); self.load_a(n & 0xFFFF, m)
            elif op == 0x0A:
                self.p = self.p & ~1 | int(bool(self.a & 0x8000)); self.load_a(self.a << 1 & 0xFFFF, m)
            elif op == 0xAA: self.x = self.a & imask; self.nz(self.x, ix)
            elif op == 0x98: self.load_a(self.y, m)
            elif op in (0xDA, 0x5A): self.push(self.x if op == 0xDA else self.y, ix)
            elif op in (0xFA, 0x7A):
                reg = 'x' if op == 0xFA else 'y'; setattr(self, reg, self.pull(ix)); self.nz(getattr(self,reg), ix)
            elif op == 0x08: self.push(self.p, 1)
            elif op == 0x28: self.set_p(self.pull(1))
            elif op == 0x8A: self.load_a(self.x, m)
            elif op == 0x4A:
                self.p = self.p & ~1 | (self.a & 1); self.load_a(self.a >> 1, m)
            elif op == 0x69:
                n = self.a + self.fetch(m) + (self.p & 1); self.p = self.p & ~1 | int(n > 0xFFFF); self.load_a(n & 0xFFFF, m)
            elif op == 0x1F: self.load_a(self.a | self.value(self.fetch(3)+self.x,m),m)
            elif op == 0x9F: self.write(self.fetch(3)+self.x,self.a,m)
            elif op == 0x6B:
                target = (self.pull(2)+1)&0xFFFF; self.pc = self.pull(1)<<16 | target

            elif op == 0x48: self.push(self.a, m)
            elif op == 0x68: self.load_a(self.pull(m), m)
            elif op in (0xA3, 0x63):
                off = self.fetch(); v = sum(self.stack[-off-i] << (8*i) for i in range(m))
                if op == 0x63:
                    n = self.a + v + (self.p & 1); self.p = self.p & ~1 | int(n > 0xFFFF); v = n & 0xFFFF
                self.load_a(v, m)
            elif op in (0xA7, 0x07):
                ptr = self.fetch(); v = self.value(self.value(ptr, 3), m)
                self.load_a(v if op == 0xA7 else self.a | v, m)
            elif op in (0xA5, 0x05, 0x15):
                addr = self.fetch() + (self.x if op == 0x15 else 0); v = self.value(addr, m)
                self.load_a(v if op == 0xA5 else self.a | v, m)
            elif op in (0x85, 0x95, 0x8D):
                addr = self.fetch(2 if op == 0x8D else 1) + (self.x if op == 0x95 else 0)
                self.write(addr, self.a, m)
            elif op == 0xE6:
                addr = self.fetch(); v = self.value(addr, m) + 1 & 0xFFFF
                self.write(addr, v, m); self.nz(v, m)
            elif op == 0xEB: self.a = (self.a >> 8) | ((self.a & 255) << 8); self.nz(self.a & 255, 1)
            elif op in (0xCA, 0x88, 0xE8):
                reg = 'y' if op == 0x88 else 'x'; v = (getattr(self, reg) + (1 if op == 0xE8 else -1)) & imask
                setattr(self, reg, v); self.nz(v, ix)
            elif op in (0x80, 0xF0, 0xD0, 0xB0, 0x10):
                n = self.fetch(); take = {0x80: True, 0xF0: bool(self.p & 2), 0xD0: not self.p & 2, 0xB0: bool(self.p & 1), 0x10: not self.p & 0x80}[op]
                if take: self.pc += n if n < 128 else n - 256
            elif op in (0xE2, 0xC2):
                v=self.fetch(); self.set_p(self.p | v if op == 0xE2 else self.p & ~v)
            elif op == 0x5C: self.pc = self.fetch(3)
            else: raise AssertionError(f'Unsupported {op:02X} at {self.pc-1:06X}')
        raise AssertionError('Converter exceeded bounded instruction count')


@unittest.skipUnless(shutil.which('asar'), 'Asar required for real converter execution')
class WallKitPaletteMaskTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kits = sorted((k for k in profiles.load_kits() if k['_row'] is not None), key=lambda k:k['_row'])
        masks = []
        for k in cls.kits:
            high = {profiles.hx(c) & 63 for s in k['sheets'] for c in s.get('high_palette_chars', [])}
            masks.extend(int(i in high) for i in range(64))
        body = routine((ROOT/'Dungeons/wall_profile_selector.asm').read_text(), 'WallSel_LoadMaskedGraphics')
        transition = routine((ROOT/'Dungeons/wall_profile_selector.asm').read_text(), 'WallSel_MaskTransitionGraphics')
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory); asm = p/'probe.asm'; rom = p/'probe.sfc'
            asm.write_text('lorom\n!WALLSEL_KIT_ROW0 = $17\n!WALLSEL_KIT_COUNT = 2\norg $44E000\nWallSel_RenderMetadata: db 0\nWallSel_KitHighPalette: db '+','.join(str(x) for x in masks)+'\norg $44E200\nProbe:\n{\n'+body+'\n}\norg $44E400\nTransitionProbe:\n{\n'+transition+'\n}\n')
            rom.write_bytes(bytes(0x240000))
            result = subprocess.run(['asar','--no-title-check','--fix-checksum=off',str(asm),str(rom)],capture_output=True,text=True)
            if result.returncode: raise AssertionError(result.stdout+result.stderr)
            cls.rom = rom.read_bytes()

    def test_actual_converter_preserves_every_unmasked_pixel_and_transparency(self):
        for kit in self.kits:
            s = next(s for s in kit['sheets'] if s['slot'] == 6)
            raw = sheet_codec.grid_to_sheet(sheet_codec.text_to_grid((profiles.KITS_DIR/s['source']).read_text()))
            high = {profiles.hx(c)&63 for c in s['high_palette_chars']}
            vm = Converter(self.rom, raw, row=kit['_row']).run()
            expected = bytearray()
            for t in range(64):
                tile = raw[t*24:(t+1)*24]; expected.extend(tile[:16])
                for y in range(8):
                    expected.extend((tile[16+y], (tile[y*2]|tile[y*2+1]|tile[16+y]) if t in high else 0))
            actual = b''.join(w.to_bytes(2,'little') for w in vm.words)
            self.assertEqual(actual, expected)
            self.assertEqual(vm.stack, [0x5A,0xC3,0xE2,0xC6])
            self.assertEqual((vm.pc,vm.p&0x30,vm.x,vm.y,vm.d,vm.db),(0xE6B6,0x30,255,255,0,0))
            self.assertEqual(vm.value(0,3),0x7E7800)
            self.assertTrue(vm.writes <= {0x7E0000,0x7E0001}|set(range(0x7E00BD,0x7E00CF)))

    def test_transition_staging_only_changes_selected_plane3_and_preserves_abi(self):
        for row in (0, 0x0B, 0x17, 0x18, 0x19, 255):
            for indoor in (0, 1):
                for status in (0x30, 0xB3):
                    vm = Converter(self.rom, bytes(1536), row=row, indoor=indoor)
                    vm.pc, vm.p = 0x44E400, status
                    vm.a, vm.x, vm.y = 0xABCD, 0, 255
                    vm.stack = [0x5A,0xC3]; vm.push(0x12,1); vm.push(0x3456,2)
                    vm.stops = (0x123457,)
                    # Native low converter produces plane3=0. Keep all other
                    # staging bytes patterned to catch collateral writes.
                    before = bytearray((i*37+11)&255 for i in range(8192))
                    for t in range(64):
                        for y in range(8): before[0x1800+t*32+17+y*2]=0
                    vm.mem.update({0x7F0000+i:v for i,v in enumerate(before)})
                    expected=bytearray(before)
                    if indoor and row in (0x17,0x18):
                        k=self.kits[row-0x17]
                        high={profiles.hx(c)&63 for s in k['sheets'] for c in s.get('high_palette_chars',[])}
                        for t in high:
                            for y in range(8):
                                p=0x1800+t*32+y*2
                                expected[p+17]=before[p]|before[p+1]|before[p+16]
                    vm.run()
                    self.assertEqual(bytes(vm.read(0x7F0000+i) for i in range(8192)),expected)
                    self.assertEqual((vm.a,vm.x,vm.y,vm.p,vm.d,vm.db),(0xABCD,0,255,status,0,0))
                    self.assertEqual(vm.stack,[0x5A,0xC3])
                    allowed={0x7F1800+t*32+16+y*2+b for t in (high if indoor and row in (0x17,0x18) else ()) for y in range(8) for b in (0,1)}
                    self.assertTrue(vm.writes <= allowed)

    def test_other_slots_rows_and_overworld_keep_native_dispatch(self):
        for row in (0,0x0B,0x17,0x18,0x19,255):
            for slot in range(8):
                for indoor in (0,1):
                    if row in (0x17,0x18) and slot==1 and indoor:continue
                    vm=Converter(self.rom,bytes(1536),row=row,slot=slot,indoor=indoor).run()
                    self.assertEqual(vm.pc,0xE5AF if slot>=4 else 0xE63C)
                    self.assertEqual(vm.words,[])
                    self.assertEqual(vm.stack,[0x5A,0xC3,0xE2,0xC6])

if __name__ == '__main__': unittest.main()
