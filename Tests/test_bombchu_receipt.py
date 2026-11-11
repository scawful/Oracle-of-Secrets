"""Actual-source, synthetic Asar/CPU controls; no game ROM or emulator socket.

The small executor implements only the independently decoded instruction set
used by these adapters. All legacy reads are compared with their displaced
native instructions, not with a second copy of the adapter algorithm.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = '30fac2f3ab6ed05b95061332d790eee2c63ce346'
# site, original bytes, receipt-index register, index scale, M width, DBR
READERS = (
    (0x07B594, 'b928b58503', 'y', 1, 8, 7),
    (0x07B5A0, 'bfe88409', 'x', 2, 8, 7),
    (0x07B5A6, 'bfe98409', 'x', 2, 8, 7),
    (0x098617, 'bde8848500', 'x', 2, 8, 9),
    (0x09861C, 'bde9848501', 'x', 2, 8, 9),
    (0x098625, 'b980858700', 'y', 1, 8, 9),
    (0x09862D, 'bde8848500', 'x', 2, 8, 9),
    (0x098632, 'bde9848501', 'x', 2, 8, 9),
    (0x098637, 'a97e8502b98085', 'y', 1, 8, 9),
    (0x09877D, 'b904848572', 'y', 1, 8, 9),
    (0x098861, 'b96c8329ff00', 'y', 1, 16, 9),
    (0x09886F, 'b9b88329ff00', 'y', 1, 16, 9),
    (0x0988CB, 'b95084f00c', 'y', 1, 8, 9),
    (0x098903, 'b96c8329ff00', 'y', 1, 16, 9),
    (0x09891C, 'b9b88329ff00', 'y', 1, 16, 9),
    (0x098A4A, 'b904848572', 'y', 1, 8, 9),
    (0x098AFD, 'b904848572', 'y', 1, 8, 9),
    (0x098BE1, 'b904848572', 'y', 1, 8, 9),
    (0x08C5C1, 'b9ddc2c9ffff', 'y', 2, 16, 8),
    (0x08C6A4, 'bf9c8409', 'x', 1, 8, 8),
    (0x08C6BA, 'bf508409', 'x', 1, 8, 8),
    (0x08C6D5, 'bf9c8409', 'x', 1, 8, 8),
    (0x06C4D6, 'bf9c8409', 'x', 1, 8, 6),
    (0x06C4E6, 'bf508409', 'x', 1, 8, 6),
)
TABLES = ((0x09836C, 76), (0x0983B8, 76), (0x098404, 76),
          (0x098450, 76), (0x09849C, 76), (0x0984E8, 152),
          (0x098580, 76), (0x07B528, 76), (0x08C2DD, 152))


def pc(at):
    assert at & 0x8000 and at >> 16 not in (0x7E, 0x7F)
    return ((at & 0x7F0000) >> 1) | (at & 0x7FFF)


class CPU:
    def __init__(self, rom, *, a=0xABCD, x=0x56, y=0x78, p=0x31, db=9):
        self.rom, self.a, self.x, self.y, self.p, self.db = rom, a, x, y, p, db
        self.d, self.stack, self.mem, self.pc = 0, [], {}, 0

    @staticmethod
    def physical(at):
        return 0x7E0000 | (at & 0xFFFF) if at >> 16 & 0x7F < 0x40 and at & 0xFFFF < 0x2000 else at

    def read(self, at, n):
        def byte(a):
            a = self.physical(a)
            if a in self.mem:
                return self.mem[a]
            if a >> 16 not in (0x7E, 0x7F) and a & 0x8000:
                return self.rom[pc(a)]
            return 0
        return sum(byte(at+i) << (8*i) for i in range(n))

    def put(self, at, value, n=1):
        for i in range(n):
            self.mem[self.physical(at+i)] = value >> (i*8) & 255

    def take(self, n=1):
        v = self.read(self.pc, n)
        self.pc += n
        return v

    def push(self, v, n):
        self.stack.extend(v.to_bytes(n, 'big'))

    def pop(self, n):
        return sum(self.stack.pop() << (8*i) for i in range(n))

    def nz(self, v, n):
        v &= (1 << (8*n))-1
        self.p = self.p & ~0x82 | (2 if not v else 0) | (0x80 if v & 1 << (8*n-1) else 0)

    def load(self, v):
        n = 1 if self.p & 0x20 else 2
        self.a = (self.a & 0xFF00 | v & 255) if n == 1 else v & 0xFFFF
        self.nz(v, n)

    def state(self):
        return self.a, self.x, self.y, self.p, self.db, self.d, self.stack, self.mem, self.pc

    def run(self, start, stops, limit=3000):
        self.pc = start
        for _ in range(limit):
            if self.pc in stops:
                return
            at = self.pc
            op = self.take()
            m, ix = (1 if self.p & 0x20 else 2), (1 if self.p & 0x10 else 2)
            if op == 0x08: self.push(self.p, 1)
            elif op == 0xC2: self.p &= ~self.take()
            elif op == 0xE2:
                self.p |= self.take()
                if self.p & 0x10: self.x &= 255; self.y &= 255
            elif op == 0x28:
                self.p = self.pop(1)
                if self.p & 0x10: self.x &= 255; self.y &= 255
            elif op in (0x48, 0xDA, 0x5A, 0x8B, 0x4B):
                value, n = {0x48:(self.a,m), 0xDA:(self.x,ix), 0x5A:(self.y,ix),
                            0x8B:(self.db,1), 0x4B:(at>>16,1)}[op]
                self.push(value & ((1 << (8*n))-1), n)
            elif op == 0xF4: self.push(self.take(2), 2)
            elif op == 0x68: self.load(self.pop(m))
            elif op in (0xFA, 0x7A, 0xAB):
                n = 1 if op == 0xAB else ix
                v = self.pop(n)
                if op == 0xFA: self.x = v
                elif op == 0x7A: self.y = v
                else: self.db = v
                self.nz(v, n)
            elif op == 0xBB: self.x = self.y & ((1 << (8*ix))-1); self.nz(self.x,ix)
            elif op in (0xC9, 0xE0, 0xC0, 0xC7, 0xD9):
                n = m if op in (0xC9, 0xC7, 0xD9) else ix
                if op == 0xC7: v = self.read(self.read(self.d+self.take(),3),m)
                elif op == 0xD9: v = self.read((self.db << 16 | self.take(2))+self.y,m)
                else: v = self.take(n)
                original = self.a if op in (0xC9,0xC7,0xD9) else self.x if op == 0xE0 else self.y
                original &= (1 << (8*n))-1
                self.p = self.p & ~1 | int(original >= v)
                self.nz(original-v,n)
            elif op == 0x89:
                self.p = self.p & ~2 | (0 if self.a & self.take(m) else 2)
            elif op in (0xD0,0xF0,0x90,0xB0,0x10,0x30,0x80):
                delta = self.take(); delta -= 256 if delta >= 128 else 0
                take = {0xD0:not self.p&2, 0xF0:bool(self.p&2), 0x90:not self.p&1,
                        0xB0:bool(self.p&1), 0x10:not self.p&0x80, 0x30:bool(self.p&0x80),0x80:True}[op]
                if take: self.pc += delta
            elif op in (0xA9,0xA2):
                v = self.take(m if op == 0xA9 else ix)
                if op == 0xA9: self.load(v)
                else: self.x = v; self.nz(v,ix)
            elif op in (0xAF,0xBF,0xAD,0xBD,0xB9,0xA5,0xA3):
                if op == 0xA3:
                    offset = self.take();v = sum(self.stack[-offset-i] << (8*i) for i in range(m))
                else:
                    if op in (0xAF,0xBF): address = self.take(3) + (self.x if op==0xBF else 0)
                    elif op == 0xA5: address = self.d+self.take()
                    else: address = (self.db << 16 | self.take(2)) + (self.x if op==0xBD else self.y if op==0xB9 else 0)
                    v = self.read(address,m)
                self.load(v)
            elif op in (0x85,0x87,0x8F,0x9F,0x83):
                if op == 0x83:
                    offset = self.take()
                    for i in range(m): self.stack[-offset-i] = self.a >> (8*i) & 255
                else:
                    if op in (0x8F,0x9F): address = self.take(3)+(self.x if op==0x9F else 0)
                    elif op == 0x87: address = self.read(self.d+self.take(),3)
                    else: address = self.d+self.take()
                    self.put(address,self.a,m)
            elif op == 0xBE:
                self.x = self.read((self.db << 16 | self.take(2))+self.y,ix); self.nz(self.x,ix)
            elif op == 0xA8: self.y = self.a & ((1 << (8*ix))-1); self.nz(self.y,ix)
            elif op == 0x4A:
                self.p = self.p & ~1 | (self.a & 1)
                self.load((self.a & ((1 << (8*m))-1)) >> 1)
            elif op in (0x64,0xE6):
                address = self.d+self.take()
                value = 0 if op == 0x64 else (self.read(address,m)+1)&((1 << (8*m))-1)
                self.put(address,value,m)
                if op == 0xE6: self.nz(value,m)
            elif op == 0x60: self.pc = self.pc & 0xFF0000 | ((self.pop(2)+1)&0xFFFF)
            elif op == 0x29: self.load(self.a & self.take(m))
            elif op == 0x18: self.p &= ~1
            elif op == 0x69:
                assert not self.p & 8, 'Grant contract requires native binary arithmetic'
                v = self.take(m); mask=(1 << (8*m))-1; a=self.a & mask
                total=a+v+(self.p&1)
                self.p=self.p & ~0x41 | int(total>mask) | (0x40 if ~(a^v)&(a^total)&(mask+1>>1) else 0)
                self.load(total & mask)
            elif op == 0xCA: self.x=(self.x-1)&((1<<(8*ix))-1);self.nz(self.x,ix)
            elif op == 0x22:
                target=self.take(3);self.push(self.pc-1,3);self.pc=target
            elif op == 0x5C: self.pc=self.take(3)
            elif op == 0x6B: self.pc=self.pop(3)+1
            elif op == 0xEA: pass
            else: raise AssertionError(f'Unsupported opcode {op:02X} at {at:06X}')
        raise AssertionError('Bounded synthetic executor exhausted')


class BombchuReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        if not cls.asar:
            raise unittest.SkipTest('Asar is required for emitted-code controls')
        cls.temp = tempfile.TemporaryDirectory(prefix='oos-bombchu-receipt-fixture-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        seed = bytearray(0x200000)
        for n,(at,count) in enumerate(TABLES):
            seed[pc(at):pc(at)+count] = bytes((i*37+n*19)&255 for i in range(count))
        for at,raw,*_ in READERS:
            seed[pc(at):pc(at)+len(bytes.fromhex(raw))] = bytes.fromhex(raw)
        seed[pc(0x00D4ED):pc(0x00D4ED)+4] = bytes.fromhex('8b4bab48')
        cls.seed = bytes(seed)
        old = subprocess.check_output(['git','-C',str(ROOT),'show',BASE+':Items/goldstar.asm'],text=True)
        current = (ROOT/'Items/goldstar.asm').read_text()
        def grant(text):
            start=text.index('ItemReceipt_KeepGoldstar:\n')
            return text[start:text.index('\npushpc\n',start)]
        cls.old_grant = grant(old).replace('ItemReceipt_KeepGoldstar','OriginalReceipt').replace('GoldstarInventory_Migrate','OriginalMigrate')
        cls.new_grant = grant(current)
        menu = (ROOT/'Menu/menu_draw.asm').read_text()
        start = menu.index('Menu_OracleTreasureOwned:\n')
        menu = menu[start:menu.index('\nendif',start)]
        cls.images = {}
        for enabled in (0,1):
            asm = (f'lorom\n!ENABLE_GOLDSTAR_CELL = {enabled}\n!BOMBCHU_AMMO_MAX = 20\n'
                   'SwitchHookOwned = $7EF3AE\nBombchuOwned = $7EF3AD\nBombchuAmmo = $7EF3B0\nGoldstarOwned = $7EF3A6\nGoldstarInventoryVersion = $7EF3A7\n'
                   'org $2B8000\n'+cls.old_grant+'OriginalEnd:\norg $2B8200\n'+cls.new_grant+'NewEnd:\n'
                   'org $09863E\nJSL ItemReceipt_KeepGoldstar\n'
                   'org $2BB400\nincsrc "'+str(ROOT/'Items/bombchu_receipt.asm')+'"\n'
                   'org $2BE000\nBombchuWorldGfx:\nincbin "'+str(ROOT/'Data/graphics/items/bombchu_world.4bpp')+'"\n'
                   'org $2BE300\n'+menu+'\n')
            cls.images[enabled] = cls.assemble(seed,asm,str(enabled))

    @classmethod
    def assemble(cls,seed,asm,name,expect_success=True):
        source=cls.folder/(name+'.asm');rom=cls.folder/(name+'.sfc');sym=cls.folder/(name+'.sym')
        source.write_text(asm);rom.write_bytes(seed)
        result=subprocess.run([cls.asar,'--no-title-check','--fix-checksum=off','--symbols=wla',
                               '--symbols-path='+str(sym),str(source),str(rom)],capture_output=True,text=True)
        if not expect_success:
            return result
        if result.returncode:
            raise AssertionError(result.stdout+result.stderr)
        labels={}
        for line in sym.read_text().splitlines():
            match=re.fullmatch(r'([0-9a-fA-F]{2}):([0-9a-fA-F]{4}) (\S+)',line)
            if match:labels[match[3]]=int(match[1]+match[2],16)
        return rom.read_bytes(),labels,asm

    def test_all_legacy_rows_match_displaced_instructions(self):
        rom,_,_=self.images[1]
        for site,raw,reg,scale,width,db in READERS:
            stops={site+len(bytes.fromhex(raw))}
            if site==0x0988CB:stops={0x0988D0,0x0988DC}
            for item in range(0x4C):
                for flags in (0,1,0x40,0x41):
                    kwargs=dict(p=0x10|(0x20 if width==8 else 0)|flags,db=db)
                    kwargs[reg]=item*scale
                    a,b=CPU(self.seed,**kwargs),CPU(rom,**kwargs)
                    for c in (a,b):c.put(0,0x7EF359,3)
                    a.run(site,stops);b.run(site,stops)
                    self.assertEqual(a.state(),b.state(),(hex(site),hex(item),flags))

    def test_executor_stack_word_layout_independent_of_receipt_code(self):
        # Native 65816 PHA pushes high then low while S decrements. Thus
        # $01,S is the low byte and $02,S the high byte. Hand-encoded ops
        # below do not assemble or call any Bombchu macro.
        rom=bytearray(0x200000);site=0x2F8000
        raw=bytes.fromhex('48a301')  # PHA; LDA $01,S, M16
        rom[pc(site):pc(site)+len(raw)]=raw
        cpu=CPU(rom,a=0x1234,p=0x10);cpu.run(site,{site+len(raw)})
        self.assertEqual(cpu.stack,[0x12,0x34])
        self.assertEqual(cpu.a,0x1234)
        raw=bytes.fromhex('830168')  # STA $01,S; PLA, M16
        rom[pc(site):pc(site)+len(raw)]=raw
        cpu=CPU(rom,a=0xBEEF,p=0x10);cpu.stack=[0x12,0x34]
        cpu.run(site,{site+2})
        self.assertEqual(cpu.stack,[0xBE,0xEF])
        cpu.run(site+2,{site+3})
        self.assertEqual((cpu.a,cpu.stack),(0xBEEF,[]))

    def test_new_row_at_every_reader_and_native_tables_unchanged(self):
        rom,labels,_=self.images[1]
        for at,n in TABLES:self.assertEqual(rom[pc(at):pc(at)+n],self.seed[pc(at):pc(at)+n])
        expected={0x07B594:255,0x07B5A0:0xAD,0x07B5A6:0xF3,0x098617:0xAD,
                  0x09861C:0xF3,0x098625:1,0x09862D:0xAD,0x098632:0xF3,
                  0x098637:1,0x09877D:0x39,0x098861:0xFC,0x09886F:0,
                  0x0988CB:2,0x098903:0xFC,0x09891C:0,0x098A4A:0x39,
                  0x098AFD:0x39,0x098BE1:0x39,0x08C5C1:0x01BD,
                  0x08C6A4:2,0x08C6BA:2,0x08C6D5:2,0x06C4D6:2,0x06C4E6:2}
        for item in (0x4C, 0x4D):
            row = dict(expected)
            if item == 0x4D:
                for site in (0x07B5A0,0x098617,0x09862D): row[site] = 0xAE
                for site in (0x09877D,0x098A4A,0x098AFD,0x098BE1): row[site] = 0x3A
                for site in (0x08C6A4,0x08C6D5,0x06C4D6): row[site] = 1
                row[0x08C5C1] = 0xFFFF  # Explicit unapproved presentation marker.
            for site,raw,reg,scale,width,db in READERS:
                # Independently execute the displaced native instruction with
                # just this new row injected into its original table address.
                ops = bytes.fromhex(raw)
                offset = 4 if site == 0x098637 else 0
                naddr = 3 if ops[offset] == 0xBF else 2
                address = int.from_bytes(ops[offset+1:offset+1+naddr], 'little')
                if naddr == 2: address |= db << 16
                address += item * scale
                oracle = bytearray(self.seed)
                oracle[pc(address):pc(address)+width//8] = row[site].to_bytes(width//8, 'little')
                for flags in (0,1,0x40,0x41):
                    kwargs=dict(p=0x10|(0x20 if width==8 else 0)|flags,db=db)
                    kwargs[reg]=item*scale
                    a,b=CPU(bytes(oracle),**kwargs),CPU(rom,**kwargs)
                    for cpu in (a,b): cpu.put(0,0x7EF359,3)
                    stops={site+len(ops),0x0988DC} if site==0x0988CB else {site+len(ops)}
                    a.run(site,stops);b.run(site,stops)
                    self.assertEqual(a.state(),b.state(),(hex(site),hex(item),flags))
        self.assertEqual(labels['SwitchHookReceiptGfxEnd']-labels['SwitchHookReceiptGfx'],128)
        self.assertLess(labels['BombchuReceipt_CodeEnd'],0x2BF000)
        # The synthetic origin reserves 189 bytes for the earlier grant delta.
        for rom,labels,_ in self.images.values():
            delta=(labels['NewEnd']-labels['ItemReceipt_KeepGoldstar'])-(labels['OriginalEnd']-labels['OriginalReceipt'])
            self.assertLessEqual(delta,0x2BB400-0x2BB343)
            self.assertEqual(rom[pc(0x09863E)],0x22)
            self.assertEqual(int.from_bytes(rom[pc(0x09863F):pc(0x098642)],'little'),labels['ItemReceipt_KeepGoldstar'])

    def test_grant_sanitizes_adds_ten_caps_and_preserves_other_inventory(self):
        for enabled,(rom,labels,_) in self.images.items():
            for ammo in range(256):
                cpu=CPU(rom,a=0xAB01,y=0x4C,p=0x30);cpu.put(0,0x7EF3AD,3)
                for at,value in ((0x7EF3B0,ammo),(0x7EF359,3),(0x7EF343,17),(0x7EF375,8)):
                    cpu.put(at,value)
                cpu.push(0x00FFEF,3);cpu.run(labels['ItemReceipt_KeepGoldstar'],{0x00FFF0})
                self.assertEqual(cpu.read(0x7EF3AD,1),1)
                self.assertEqual(cpu.read(0x7EF3B0,1),min((ammo if ammo<=20 else 0)+10,20))
                self.assertEqual([cpu.read(a,1) for a in (0x7EF359,0x7EF343,0x7EF375)],[3,17,8])
                self.assertEqual((cpu.x,cpu.y,cpu.db,cpu.d,cpu.stack),(0x56,0x4C,9,0,[]))

    def test_switch_hook_generic_grant_changes_only_existing_ownership(self):
        for enabled,(rom,labels,_) in self.images.items():
            cpu=CPU(rom,a=0xAB01,y=0x4D,p=0x30);cpu.put(0,0x7EF3AE,3)
            # Already-migrated inventory: migration itself is covered above/below.
            for at,value in ((0x7EF342,2),(0x7EF3A7,0xA5),(0x7EF3AD,1),(0x7EF3B0,17),(0x7EF359,3)):
                cpu.put(at,value)
            before=dict(cpu.mem)
            cpu.push(0x00FFEF,3);cpu.run(labels['ItemReceipt_KeepGoldstar'],{0x00FFF0})
            self.assertEqual(cpu.read(0x7EF3AE,1),1)
            self.assertEqual(cpu.mem,{**before,0x7EF3AE:1})
            self.assertEqual((cpu.a,cpu.x,cpu.y,cpu.db,cpu.d,cpu.stack),(0xAB01,0x56,0x4D,9,0,[]))

    def test_existing_goldstar_hook_behavior_is_exact_for_every_legacy_id(self):
        for enabled,(rom,labels,_) in self.images.items():
            for item in range(0x4C):
                for value in (0,1,2,0xFF):
                    for version in (0,0xA5):
                        for ownership in (0,1,2):
                            cpus=[CPU(rom,a=0xAB00|value,y=item,p=0x30|(0x80 if value&0x80 else 0)) for _ in range(2)]
                            for cpu,label in zip(cpus,('OriginalReceipt','ItemReceipt_KeepGoldstar')):
                                cpu.put(0,0x7EF342,3);cpu.put(0x7EF342,ownership);cpu.put(0x7EF3A7,version)
                                cpu.push(0x00FFEF,3);cpu.run(labels[label],{0x00FFF0})
                            self.assertEqual(cpus[0].state(),cpus[1].state(),(enabled,item,value,version,ownership))

    def test_art_copies_exact_existing_frame_and_legacy_entry_is_unchanged(self):
        rom,labels,_=self.images[1]
        for selector,filename in ((0x39,'bombchu_world.4bpp'),(0x3A,'switch_hook_receipt.4bpp')):
            for flags in (0x30,0x31,0x70,0x71):
                cpu=CPU(rom,a=0xAB00|selector,x=0x34,y=0x56,p=flags,db=0x17)
                cpu.put(0x7EBD3F,0xAA);cpu.put(0x7EBDC0,0xBB)
                cpu.push(0x00FFEF,3);cpu.run(0x00D4ED,{0x00FFF0})
                art=(ROOT/'Data/graphics/items'/filename).read_bytes()[:128]
                self.assertEqual(bytes(cpu.read(0x7EBD40+i,1) for i in range(128)),art)
                self.assertEqual((cpu.read(0x7EBD3F,1),cpu.read(0x7EBDC0,1)),(0xAA,0xBB))
                self.assertEqual((cpu.a,cpu.x,cpu.y,cpu.p,cpu.db,cpu.d,cpu.stack),
                                 (0xAB00|selector,0x34,0x56,flags,0x17,0,[]))
        for selector in range(256):
            if selector in (0x39,0x3A): continue
            for flags in (0x30,0x31,0x70,0x71):
                a,b=CPU(self.seed,a=0xAB00|selector,p=flags,db=0x17),CPU(rom,a=0xAB00|selector,p=flags,db=0x17)
                a.run(0x00D4ED,{0x00D4F1});b.run(0x00D4ED,{0x00D4F1})
                self.assertEqual(a.state(),b.state(),(selector,flags))

    def test_menu_boolean_and_equipment_levels_from_assembled_body(self):
        rom,labels,_ = self.images[1]
        # Explicit boundary vectors, executing production ASM (no Python predicate).
        cases = [(4,0xAE,0,0),(4,0xAE,1,1),(4,0xAE,2,0),(4,0xAE,255,0),
                 (0,0x5A,2,0),(0,0x5A,3,1),(0,0x5A,255,1),
                 (0x10,0x59,1,0),(0x10,0x59,2,1),(0x10,0x59,3,1),
                 (6,0x54,0,0),(6,0x54,1,1),(6,0x54,2,1)]
        for dungeon,sram,value,want in cases:
            cpu=CPU(rom,p=0x31,db=0x17)
            cpu.put(0x040C,dungeon);cpu.put(0x7EF300+sram,value)
            cpu.put(2,0xAA);cpu.put(3,0xBB)
            cpu.push(0xFFEF,2)
            cpu.run(labels['Menu_OracleTreasureOwned'],{0x2BFFF0})
            self.assertEqual((cpu.read(2,1),cpu.read(3,1)),(want,0),(dungeon,value))
            self.assertEqual((cpu.db,cpu.d,cpu.stack,cpu.p&0x30),(0x17,0,[],0x30))

    def test_menu_executor_opcodes_have_direct_controls(self):
        rom=bytearray(0x200000);at=0x2FE000
        # LSR A; TAY; LDX $1000,Y; CMP $1001,Y; STZ $02; INC $02; RTS.
        raw=bytes.fromhex('4aa8be0010d901106402e60260')
        rom[pc(at):pc(at)+len(raw)]=raw
        cpu=CPU(bytes(rom),a=0xAB05,p=0x70,db=0x17)
        cpu.put(0x171002,0x81);cpu.put(0x171003,2)
        cpu.put(2,0xFF);cpu.push(0xFFEF,2)
        cpu.run(at,{at+2})
        self.assertEqual((cpu.a,cpu.y,cpu.p&1),(0xAB02,2,1))
        cpu.run(at+2,{at+5})
        self.assertEqual((cpu.x,cpu.p&0x80),(0x81,0x80))
        cpu.run(at+5,{at+8})
        self.assertEqual((cpu.a,cpu.p&0x83),(0xAB02,3))
        cpu.run(at+8,{at+10})
        self.assertEqual((cpu.read(2,1),cpu.p&0x83),(0,3))
        cpu.run(at+10,{0x2FFFF0})
        self.assertEqual((cpu.read(2,1),cpu.p&0x83,cpu.stack),(1,1,[]))

    def test_every_stale_hook_preimage_refuses_assembly(self):
        _,_,asm=self.images[1]
        for site,raw,*_ in (*READERS,(0x00D4ED,'8b4bab48')):
            seed=bytearray(self.seed);seed[pc(site)]^=1
            result=self.assemble(seed,asm,f'stale-{site:06X}',expect_success=False)
            self.assertNotEqual(result.returncode,0,hex(site))
            self.assertIn('preimage changed',result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
