#!/usr/bin/env python3
"""Compile actual Farore helper and execute with existing Lakesnes CPU fixture.
DMA is recorded/emulated at register level; no PPU/native rendering claim.
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
ROWS = [0x1500, 0x1700, 0x1540, 0x1740, 0x1580, 0x1780, 0x1000,
        0x1200, 0x1040, 0x1240, 0x1080, 0x1280, 0x1400, 0x1600]
MEMBERS = set(range(0x90, 0x96)) | {0xA0, 0xA6, 0xA7, 0xB0}
HOOKS = {0x028A97: 0x00E031, 0x028D10: 0x00E031, 0x0294E6: 0x00E031,
         0x028286: 0x00E19B, 0x029BA7: 0x00E19B, 0x0AEF48: 0x00E19B}


def pc(address):
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def assemble(folder, enabled, source=None):
    folder.mkdir()
    initial = bytearray(b'\xff' * 0x200000)
    for address, target in HOOKS.items():
        initial[pc(address):pc(address)+4] = b'\x22'+target.to_bytes(3, 'little')
    initial[pc(0x01B63A):pc(0x01B641)] = bytes.fromhex('bf63d40e8dae0a')
    for i in range(0x100):
        initial[pc(0x0ED460)+i] = (i*13+7) & 255
    image = folder/'fixture.sfc'
    image.write_bytes(initial)
    asm = folder/'fixture.asm'
    helper = ROOT/'Sprites/NPCs/farore_d8_graphics.asm'
    if source is not None:
        helper = folder/'mutated.asm'
        helper.write_text(source)
    draw = (ROOT/'Sprites/NPCs/farore.asm').read_text().split('Sprite_Farore_Draw:',1)[1]
    draw_source = 'Sprite_Farore_Draw:'+draw
    fields = '\n'.join(m[0] for m in re.finditer(r'(?m)^Spr[A-Z]\w*\s*=\s*\$[0-9a-fA-F]+', (ROOT/'Core/symbols.asm').read_text()))
    asm.write_text(fields+'\nSprite_Farore = $73\nInCutScene = $7EF303\nSprite_GetTileAttr = $06E87B\n'+f'lorom\n!ENABLE_D8_FARORE_GRAPHICS = {enabled}\norg $308000\nincsrc "{helper}"\n'+
                   ('Sprite_PrepOamCoord = $018000\nSprite_OAM_AllocateDeferToPlayer = $018010\n'+draw_source+'\nincsrc "'+str(ROOT/'Sprites/NPCs/farore_d8_follow.asm')+'"\n' if enabled else ''))
    result = subprocess.run(['asar', '-I'+str(ROOT), '--no-title-check', '--fix-checksum=off',
                             '--symbols=wla', str(asm), str(image)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout+result.stderr
    labels = {m[3]: int(m[1]+m[2], 16) for m in re.finditer(
        r'(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$', image.with_suffix('.sym').read_text())}
    return image.read_bytes(), labels, bytes(initial)


class GraphicsFixture(Fixture):
    def __init__(self, *args):
        self.io = {}; self.dma = []; self.vram = bytearray((i*7+31) & 255 for i in range(65536))
        super().__init__(*args)
        self.stubs = {0x00E031: 'convert', 0x00E19B: 'full_load'}

    def write(self, address, value):
        if address in (0x2115, 0x2116, 0x2117, 0x420B) or 0x4300 <= address <= 0x4306:
            self.io[address] = value
            if address == 0x420B:
                assert value == 1 and self.io[0x2115] == 0x80
                assert self.io[0x4300] == 1 and self.io[0x4301] == 0x18
                src = self.io[0x4302] | self.io[0x4303] << 8 | self.io[0x4304] << 16
                size = self.io[0x4305] | self.io[0x4306] << 8
                dst = (self.io[0x2116] | self.io[0x2117] << 8) * 2
                self.vram[dst:dst+size] = bytes(self.read(src+i) for i in range(size))
                self.dma.append((src, dst, size))
            return
        super().write(address, value)

    def stub(self, name):
        if name not in ('convert', 'full_load'):
            super().stub(name)
            return
        self.calls.append(name)
        # These wrappers must overlay AFTER the native conversion/full upload.
        if name == 'convert':
            self.ram[0x10000:0x12000] = bytes((i*17+43) & 255 for i in range(8192))
        elif name == 'full_load':
            self.vram[:] = bytes((i*7+31) & 255 for i in range(65536))


def call(f, name, m8=True, x8=True, a=0xA75D, x=0x37, y=0x4B, db=0x7E):
    c = f.cpu
    c.a=a; c.x=x; c.y=y; c.db=db; c.mf=m8; c.xf=x8; c.c=True
    c.sp=0x1FF
    address=f.addr(name); c.k=address >> 16; c.pc=address & 65535
    f.put(0x1FF, c.k); f.put(0x1FE, 0x6F); f.put(0x1FD, 0xFF); c.sp=0x1FC
    for _ in range(30000):
        current=c.k << 16 | c.pc
        if current == (address & 0xFF0000) | 0x7000:
            assert not f.bad_writes, f.bad_writes
            assert (c.sp,c.x,c.y,c.db,c.mf,c.xf)==(0x1FF,x,y,db,m8,x8), name
            return c.a
        if current in f.stubs: f.stub(f.stubs[current])
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError((name, 'instruction limit', hex(current)))


def setup(f, room=0x90, indoor=1, crystal=0):
    f.word(0xA0,room); f.put(0x1B,indoor); f.put(0x7EF37A,crystal)
    f.put(0x13,0x80); f.put(0x412,9); f.put(0x0AB1,0x0A)
    f.put(0x7EC2FE,0x29); f.put(0x7EC2FF,0x52)


def buffer_expected(blob, selected):
    expected=bytearray((i*17+43) & 255 for i in range(8192))
    if selected:
        for row,dst in enumerate(ROWS): expected[dst:dst+64]=blob[row*64:(row+1)*64]
    return expected


def check(lib, rom, labels, blob):
    cases=[]
    for room in list(range(0x128))+[0x190,0x1A0]:
        f=GraphicsFixture(lib,rom,labels)
        try:
            setup(f,room)
            assert call(f,'D8Farore_IsMember',m8=False,x8=False,x=0x183,y=0x1A2)==0xA75D
            assert f.cpu.c==(room in MEMBERS), hex(room)
        finally: f.close()
    cases.append('298 full-width membership and ABI cases')
    for room,indoor,crystal in [(r,1,0) for r in sorted(MEMBERS)]+[(0x96,1,0),(0x190,1,0),(0x90,0,0),(0x90,1,0x80),(0x90,1,0x7F)]:
        selected=room in MEMBERS and indoor and not crystal & 0x80
        for name in ('D8Farore_LoadSet','D8Farore_InitializeTilesets'):
            f=GraphicsFixture(lib,rom,labels)
            try:
                setup(f,room,indoor,crystal)
                result=call(f,name)
                assert result==0xA75D and f.cpu.c, 'post-native CPU state changed'
                if name=='D8Farore_LoadSet':
                    assert f.calls==['convert']
                    assert f.ram[0x10000:0x12000]==buffer_expected(blob,selected)
                    assert not f.dma
                else:
                    assert f.calls==['full_load']
                    expected=bytearray((i*7+31)&255 for i in range(65536))
                    if selected:
                        for row,dst in enumerate(ROWS):expected[0xA000+dst:0xA000+dst+64]=blob[row*64:(row+1)*64]
                    assert f.vram==expected, 'VRAM write outside selected rows or wrong bytes'
                    assert len(f.dma)==(14 if selected else 0)
                    assert all(size==64 for _,_,size in f.dma)
                assert [f.get(a) for a in (0x412,0xAB1,0x7EC2FE,0x7EC2FF)]==[9,10,0x29,0x52]
                allowed=set(range(0x100,0x200))
                assert all((addr&0xFFFFFF) in allowed or 0x7F1000<=addr<0x7F1800 or addr in (0xA0,0xA1,0x1B,0x7EF37A,0x13,0x412,0xAB1,0x7EC2FE,0x7EC2FF) for addr,_ in f.writes)
                cases.append(f'{name}-{room:03X}-{indoor}-{crystal:02X}')
            finally:f.close()
    for brightness in (0,15,127):
        f=GraphicsFixture(lib,rom,labels)
        try:
            setup(f);f.put(0x13,brightness);call(f,'D8Farore_OverlayVram')
            assert not f.io and f.get(0x13)==brightness
        finally:f.close()
    cases.append('3 nonblank DMA refusals')
    for hdma in (1,0x81,0xC0):
        f=GraphicsFixture(lib,rom,labels)
        try:
            setup(f);f.put(0x9B,hdma);call(f,'D8Farore_OverlayVram')
            assert len(f.dma)==(0 if hdma&1 else 14)
            assert f.get(0x9B)==hdma
        finally:f.close()
    cases.append('HDMA0 refuses; unrelated channels remain owned by engine')
    for room,indoor,crystal in [(0x90,1,0),(0x96,1,0),(0x90,0,0),(0x90,1,0x80)]:
        f=GraphicsFixture(lib,rom,labels)
        try:
            setup(f,room,indoor,crystal)
            original=rom[pc(0x0ED463)+0x34]
            before=bytes(f.ram)
            result=call(f,'D8Farore_HeaderPalette',x8=False,x=0x34,y=0x137,db=0x01)
            assert result==0xA700|original, 'displaced header A changed'
            assert f.get(0x0AAE)==(3 if room==0x90 and indoor and not crystal else original)
            assert f.get(0x0AB1)==0x0A
            assert all(old==new or i==0xAAE or 0x100<=i<0x200 for i,(old,new) in enumerate(zip(before,f.ram))), 'header altered unrelated memory'
        finally:f.close()
    cases.append('header full X/Y preserved; aux2 only, no environment write')
    for selected in (False,True):
        for tile in range(256):
            f=GraphicsFixture(lib,rom,labels)
            try:
                setup(f,0x90 if selected else 0x96)
                result=call(f,'D8Farore_RemapTile',a=0xA700|tile)
                expect={0x86:0x80,0x88:0x82,0x8A:0x84,0x8C:0xA0}.get(tile,tile) if selected else tile
                assert result==0xA700|expect and f.cpu.c
                result=call(f,'D8Farore_RemapPalette',a=0xA700|tile)
                expect=(tile & 0xF1)|0x0C if selected else tile
                assert result==0xA700|expect and f.cpu.c
            finally:f.close()
    cases.append('1024 remap/props cases preserve upper A and P')
    chars=[0xA8,0xAA,0xA8,0x88,0xAA,0xA8,0x8A,0x8C,0x8C,0x8A,0x8A,0xAC,0xAA,0x86]
    props=[0x3B,0x3B,0x3B,0x7B,0x3B,0x3B,0x3B,0x3B,0x7B,0x3B,0x3B,0x3B,0x3B,0x7B]
    for frame in range(7):
        outputs=[]
        for selected in (False,True):
            f=GraphicsFixture(lib,rom,labels)
            try:
                setup(f,0x90 if selected else 0x96)
                f.stubs={0x018000:'Sprite_PrepOamCoord',0x018010:'Sprite_OAM_AllocateDeferToPlayer'}
                f.cpu.db=0x30;f.put(0xDC6,frame);f.put(0xD96,0)
                f.call('Sprite_Farore_Draw')
                output=bytes(f.ram[0x800:0x808]);outputs.append(output)
                for slot,idx in enumerate((frame*2+1,frame*2)):
                    tile=chars[idx];prop=props[idx]
                    if selected:
                        tile={0x86:0x80,0x88:0x82,0x8A:0x84,0x8C:0xA0}.get(tile,tile)
                        prop=(prop&0xF1)|0x0C
                    assert output[slot*4+2:slot*4+4]==bytes([tile,prop])
                assert f.ram[0xA00:0xA02]==bytes([2,2])
            finally:f.close()
        assert all(outputs[0][i]==outputs[1][i] for i in (0,1,4,5)), 'frame geometry changed'
    cases.append('14 actual Farore draw frames, geometry/size/flip preservation')
    return cases


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lakesnes',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();blob=(ROOT/'Sprites/NPCs/Data/farore_d8_low.4bpp').read_bytes()
    assert len(blob)==896 and hashlib.sha256(blob).hexdigest()=='315e544895aebbac94ea652aab5008e29f64439e159114e8da3292c299b911ae'
    for file in ('Util/macros.asm','Config/feature_flags.asm'):
        assert re.search(r'^!ENABLE_D8_FARORE_GRAPHICS\s*=\s*0\b',(ROOT/file).read_text(),re.M)
    with tempfile.TemporaryDirectory(prefix='oos-farore-graphics-') as temp:
        p=Path(temp);libfile=p/'cpu.dylib'
        subprocess.run(['cc','-shared','-fPIC','-O2',str(args.lakesnes/'snes/cpu.c'),str(args.lakesnes/'snes/statehandler.c'),'-o',str(libfile)],check=True)
        lib=C.CDLL(str(libfile));lib.cpu_init.restype=C.POINTER(Cpu);lib.cpu_runOpcode.argtypes=[C.POINTER(Cpu)];lib.cpu_free.argtypes=[C.POINTER(Cpu)]
        off,_,initial=assemble(p/'off',0);assert off==initial,'flag off emitted bytes'
        rom,labels,_=assemble(p/'on',1)
        cases=check(lib,rom,labels,blob)
        size=labels['D8Farore_GraphicsEnd']-labels['D8Farore_GraphicsStart']
        support_size=labels['D8Farore_SupportEnd']-labels['D8Farore_GraphicsStart']
        assert support_size<=2048
        for address,target in HOOKS.items():
            expected=labels['D8Farore_LoadSet' if target==0x00E031 else 'D8Farore_InitializeTilesets']
            assert rom[pc(address):pc(address)+4]==b'\x22'+expected.to_bytes(3,'little')
        # Mutation controls: room96 inclusion and one wrong destination must fail.
        controls=[];source=(ROOT/'Sprites/NPCs/farore_d8_graphics.asm').read_text()
        for name,old,new in [('member96','CMP.w #$0096','CMP.w #$0097'),('row-destination','STA.l $7F1500,X','STA.l $7F1540,X')]:
            mutant,mutlabels,_=assemble(p/name,1,source.replace(old,new,1))
            try:check(lib,mutant,mutlabels,blob)
            except AssertionError:controls.append(name)
            else:raise AssertionError('mutation not detected: '+name)
    result={'status':'PASS','source_sha256':hashlib.sha256(source.encode()).hexdigest(),'blob_sha256':hashlib.sha256(blob).hexdigest(),'slot_bytes':support_size,'graphics_bytes':size,'slot_capacity':2048,'checks':cases,'mutation_controls':controls,'scope':'compiled CPU, stubbed native load, emulated DMA registers; no native PPU/render or whole-game build'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'PASS','slot_bytes':support_size,'graphics_bytes':size,'check_groups':len(cases),'mutation_controls':controls}))

if __name__=='__main__':main()
