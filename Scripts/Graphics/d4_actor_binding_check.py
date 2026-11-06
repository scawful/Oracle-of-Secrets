#!/usr/bin/env python3
"""Read back D4 native actor binding from a compiled private ROM. No writes to ROM.

Compare compiled pointer rows, compressed pages, palettes and OAM tables with
the accepted candidate. This is compiled-data/render proof, not CPU/runtime proof.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Scripts/Generate'))
import lz2, sheet_codec
from sheet_table import pc, decomp, ptr

ROWS={'protector_head':3,'protector_body':4,'warden_armor':5,'warden_iron':6}
RESERVED={0x20:'Baby',0x22:'Baby',0xC0:'Princess',0xC2:'Princess',0xE0:'Princess',0xE2:'Princess'}

def rgb(w):return tuple(((w>>s)&31)*255//31 for s in (0,5,10))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('rom','symbols','candidate','base','output'):ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();assert not args.output.exists(),'fresh output required'
    rom=args.rom.read_bytes();base=args.base.read_bytes();r=json.loads((args.candidate/'RECEIPT.json').read_text())
    assert hashlib.sha256(base).hexdigest()==r['base_sha256']
    labels={}
    for line in args.symbols.read_text().splitlines():
        m=re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)',line)
        if m:labels[m[3]]=int(m[1]+m[2],16)
    def address(name):return labels.get('Oracle_'+name,labels.get(name))
    def data(name,n):
        a=address(name);assert a is not None,name+' missing from symbols'
        return rom[pc(a):pc(a)+n]
    pages=[];streams=[]
    for i,global_id in enumerate(range(0xDF,0xE3)):
        p=sum(data(name,256)[global_id]<<shift for name,shift in [('GfxSheet_Bank',16),('GfxSheet_High',8),('GfxSheet_Low',0)])
        raw,used=lz2.decompress(rom[pc(p):],max_output=1536)
        assert raw==(args.candidate/f'actor-page-{i}.3bpp').read_bytes()
        assert p&0x7FFFFF==address(f'SourceGlobalSheet_{global_id:02X}')&0x7FFFFF
        assert (p>>16)&0x7F==0x47
        pages.append(sheet_codec.sheet_to_grid(raw));streams.append(dict(global_sheet=f'{global_id:02X}',relative_sheet=f'{global_id-0x73:02X}',snes=f'{p:06X}',bytes=used,sha256=hashlib.sha256(raw).hexdigest()))
    group_pc=0x5B57+(64+0x4F)*4
    assert rom[group_pc:group_pc+4]==bytes.fromhex('6c6d6e6f')
    palette={name:[0]+[int.from_bytes(data('D4Zora_Palette_'+name,14)[i:i+2],'little') for i in range(0,14,2)] for name in ROWS}
    assert {name:[f'{v:04X}' for v in words] for name,words in palette.items()}==r['palettes']
    # Verify the complete compiled palette writer, including its exact 8 STA.l
    # destinations. Only 7 words per lower half, in both source/display buffers.
    expected=b'\xDA\xC2\x20\xA2\x0C'
    writes=[]
    for name,row in ROWS.items():
        expected+=b'\xBF'+address('D4Zora_Palette_'+name).to_bytes(3,'little')
        for start in (0x7EC400,0x7EC600):
            dest=start+row*32+2;writes.extend(dest+i for i in range(0,14,2))
            expected+=b'\x9F'+dest.to_bytes(3,'little')
    branch=5-(len(expected)+4)
    expected+=bytes([0xCA,0xCA,0x10,branch&255])+b'\xE2\x20\xE6\x15\xFA\x60'
    assert data('D4Zora_LoadPalettes',len(expected))==expected,'palette writer differs from reviewed bounded stores'
    assert address('D4Zora_LoadPalettes')+len(expected)==address('D4Zora_Draw')
    starts=data('D4Zora_FrameStarts',len(r['frames']));counts=data('D4Zora_FrameCounts',len(r['frames']))
    total=sum(counts);chars=data('D4Zora_Chars',total);props=data('D4Zora_Props',total)
    xraw=data('D4Zora_XOffsets',total*2);yraw=data('D4Zora_YOffsets',total*2)
    palettes_by_row={ROWS[n]:p for n,p in palette.items()};use={};results=[];images={}
    for n,(name,frame) in enumerate(r['frames'].items()):
        assert counts[n]==len(frame['oam'])
        ox,oy=(-16,-40) if name.startswith('warden') else (-8,-16)
        image=Image.new('RGBA',tuple(frame['canvas']));entries=[]
        for j,entry in enumerate(frame['oam']):
            i=starts[n]+j;char=chars[i];prop=props[i]
            x=int.from_bytes(xraw[i*2:i*2+2],'little',signed=True);y=int.from_bytes(yraw[i*2:i*2+2],'little',signed=True)
            assert (char,x,y,prop)==(entry['char'],entry['x']+ox,entry['y']+oy,0x31|(ROWS[entry['palette']]<<1))
            assert char not in RESERVED and prop&1 and prop>>6==0
            use.setdefault(char,entry['palette']);entries.append((char,x-ox,y-oy,palettes_by_row[(prop>>1)&7]))
        for char,x,y,pal in reversed(entries):
            sheet=pages[char>>6];tx,ty=(char&15)*8,((char&63)//16)*8
            for yy in range(16):
                for xx in range(16):
                    v=sheet[ty+yy][tx+xx]
                    if v:image.putpixel((x+xx,y+yy),rgb(pal[v])+(255,))
        assert image.tobytes()==Image.open(args.candidate/(name+'-native.png')).convert('RGBA').tobytes(),name+' compiled composition differs'
        results.append(name);images[name]=image
    princess,_=decomp(base,ptr(base,0x56+0x73));original=sheet_codec.sheet_to_grid(princess)
    for t in [*range(4),*range(16,20),*range(32,36),*range(48,52)]:
        x,y=(t%16)*8,(t//16)*8
        assert all(pages[3][y+j][x:x+8]==original[y+j][x:x+8] for j in range(8))
    args.output.mkdir(parents=True)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',22)
    small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
    board=Image.new('RGB',(1380,1070),'#252a2d');d=ImageDraw.Draw(board)
    d.text((24,14),'D4 private ROM — compiled graphics page readback',font=font,fill='white')
    d.text((24,48),'Spriteset $4F selects $6C/$6D/$6E/$6F; global sheets $DF/$E0/$E1/$E2 in bank $47.',font=small,fill='#cad3cc')
    free=[]
    for page,sheet in enumerate(pages):
        top=90+page*220
        d.text((24,top),f'Page {page}: global ${0xDF+page:02X} / relative ${0x6C+page:02X} / chars ${page*64:02X}–${page*64+63:02X}',font=small,fill='white')
        for cell in range(16):
            char=page*64+(cell//8)*32+(cell%8)*2;xx=24+(cell%8)*78;yy=top+30+(cell//8)*82
            role=use.get(char);reserved=RESERVED.get(char)
            colour='#70a9d3' if reserved=='Princess' else '#e4ac55' if reserved else '#a0c49d' if not role else '#7c8985'
            if not role and not reserved:free.append(f'{char:02X}')
            d.rectangle((xx,yy,xx+65,yy+65),outline=colour,width=1)
            pal=palette[role] if role else [0]+[0x0842*i for i in range(1,8)]
            tx,ty=(char&15)*8,((char&63)//16)*8
            for y in range(16):
                for x in range(16):
                    v=sheet[ty+y][tx+x]
                    if v:d.rectangle((xx+1+x*4,yy+1+y*4,xx+4+x*4,yy+4+y*4),fill=rgb(pal[v]))
            d.text((xx+66,yy),f'{char:02X}',font=small,fill=colour)
    for i,(name,row) in enumerate(ROWS.items()):
        y=110+i*100;d.text((710,y),f'OBJ row {row}: {name.replace("_"," ")}',font=small,fill='white')
        for j,w in enumerate(palette[name][1:]):d.rectangle((710+j*46,y+29,749+j*46,y+58),fill=rgb(w))
    for i,line in enumerate(('Cell colours show the first consumer palette.','Blue border: preserved Princess cells.','Amber border: reserved Baby upload cells.',f'Free cells: {", ".join(free)}','Colours 8–15 and OBJ rows 1/7 untouched.','9 compiled pose compositions match accepted art.','Compiled data/render proof; not a runtime capture.')):
        d.text((710,560+i*35),line,font=small,fill='#cad3cc')
    d.text((24,1010),'52 actor cells + 6 reserved cells + 6 free cells = 64 total 16x16 cells.',font=font,fill='white')
    board.save(args.output/'compiled-tilesheet-map.png')
    for name,image in images.items():image.save(args.output/(name+'-compiled.png'))
    report=dict(status='COMPILED_BINDING_RENDER_PASS',rom_sha256=hashlib.sha256(rom).hexdigest(),symbols_sha256=hashlib.sha256(args.symbols.read_bytes()).hexdigest(),
                candidate_receipt_sha256=hashlib.sha256((args.candidate/'RECEIPT.json').read_bytes()).hexdigest(),streams=streams,
                frames_exact=results,palette_rows=ROWS,palette_word_destinations=[f'{a:06X}' for a in writes],
                bounded_palette_writer_exact=True,princess_cells_exact=True,baby_upload_slots_reserved=True,free_obj_cells=free,
                native_runtime_qualified=False)
    (args.output/'RECEIPT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','rom_sha256','frames_exact','free_obj_cells','native_runtime_qualified')},indent=2))

if __name__=='__main__':main()
