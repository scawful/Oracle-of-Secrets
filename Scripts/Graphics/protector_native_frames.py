#!/usr/bin/env python3
"""Trace the approved River Protector concept into unbound native NPC frames.

No ROM writes or allocation. Sample the approved concept's large pixel cells,
assign explicit SNES colour roles, and use the existing sheet codec. Head/body
palettes share every entry except slot 5 (yellow fins / brown strap).
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Scripts/Generate'))
import sheet_codec

CONCEPT_SHA = '1b109a71770a10c8dcc8d68969b4bc042b79767b72b2a007d59edabcab84b2cb'
PLAYER_SHA = '43f78dd7593a25111dfb5d6ba37b2981ccf03741a100cb8cab7dfafe56c51085'
# Logical palettes; no hardware palette rows or global sheet IDs are assigned.
HEAD = [0x0000,0x0C63,0x2525,0x39E5,0x46F0,0x2F7D,0x5B7D,0x1ADF]
BODY = [*HEAD]; BODY[5] = 0x1970
TRACE = {'front':dict(x=312,y=264,dx=24.5,dy=24),
         'side':dict(x=836,y=264,dx=24.5,dy=24)}
FIN_TIPS = {'front':((2,8),(13,8),(1,10),(14,10)),
            'side':((2,5),(1,9),(2,9))}

def rgb(word):
    return tuple(((word>>s)&31)*255//31 for s in (0,5,10))

def save_grid(grid,path,palette):
    im=Image.new('P',(len(grid[0]),len(grid)))
    colours=[rgb(w) for w in palette]
    im.putpalette([v for c in colours for v in c]+[0]*(768-len(colours)*3))
    im.putdata([v for row in grid for v in row]); im.info['transparency']=0
    im.save(path)
    return im.convert('RGBA')

def trace(concept,spec,fin_tips):
    # Eight opaque semantic roles are split between two seven-colour palettes.
    roles=[rgb(w) for w in HEAD]+[rgb(BODY[5])]
    grid=[[0]*16 for _ in range(24)]
    for y in range(19):
        for x in range(16):
            point=(round(spec['x']+(x+.5)*spec['dx']),round(spec['y']+(y+.5)*spec['dy']))
            colour=concept.getpixel(point)
            if max(colour)-min(colour)<18 and min(colour)>70:
                continue  # neutral-grey concept background
            # Ignore interpolation/texture within a sampled concept cell.
            role=min(range(1,9),key=lambda i:sum((a-b)**2 for a,b in zip(colour,roles[i])))
            # Tiny eye-outline shadows use the native dark outline, not a third OBJ.
            if role==8 and y+2<8:role=1
            # The concept's pale body/foot highlights remain cream, not fin yellow.
            if role==5 and y+2>=16:role=6
            grid[y+2][x]=role
    # Preserve the approved semantic distinction after SNES quantization:
    # yellow belongs to lateral fins; the close amber muzzle highlight does not.
    for y,row in enumerate(grid):
        for x,v in enumerate(row):
            if v==5 and (x,y) not in fin_tips:row[x]=7
    for x,y in fin_tips:
        assert grid[y][x], 'fin tracing must not add a new silhouette cell'
        grid[y][x]=5
    return grid

def split_tiles(frame):
    head=[[0]*16 for _ in range(16)]
    body=[[0]*16 for _ in range(16)]
    for y,row in enumerate(frame):
        for x,v in enumerate(row):
            if not v:continue
            if y<14 and v!=8:head[y][x]=v
            if y>=8 and v!=5:body[y-8][x]=5 if v==8 else v
            if y<8:assert v!=8, 'unrepresentable upper-head strap colour'
            if y>=14:assert v!=5, 'yellow outside head tile'
    return head,body

def compose(head,body):
    # Earlier head OBJ wins overlap, as on SNES. Palettes are resolved per OBJ.
    output=Image.new('RGBA',(16,24))
    for tile,offset,palette in ((body,8,BODY),(head,0,HEAD)):
        for y,row in enumerate(tile):
            for x,v in enumerate(row):
                if v:output.putpixel((x,y+offset),rgb(palette[v])+(255,))
    return output

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--concept',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--link-reference',type=Path,required=True)
    args=ap.parse_args()
    assert not args.output.exists(), 'fresh output directory required'
    data=args.concept.read_bytes();assert hashlib.sha256(data).hexdigest()==CONCEPT_SHA
    concept=Image.open(args.concept).convert('RGB');assert concept.size==(1536,1024)
    player=(ROOT/'Masks/gfx/zora_link.4bpp').read_bytes()
    assert hashlib.sha256(player).hexdigest()==PLAYER_SHA
    out=args.output;out.mkdir(parents=True)
    sheet=[[0]*128 for _ in range(32)]
    frames={}; previews={}
    for n,(name,spec) in enumerate(TRACE.items()):
        grid=trace(concept,spec,FIN_TIPS[name]);head,body=split_tiles(grid)
        result=compose(head,body)
        # Full trace has role 8 for strap brown. Prove OBJ composition preserves it.
        for y,row in enumerate(grid):
            for x,v in enumerate(row):
                expected=(0,0,0,0) if not v else rgb(BODY[5] if v==8 else HEAD[v])+(255,)
                assert result.getpixel((x,y))==expected,(name,x,y,v)
        result.save(out/f'{name}-native.png')
        result.resize((128,192),Image.Resampling.NEAREST).save(out/f'{name}-8x.png')
        (out/f'{name}-roles.txt').write_text('\n'.join(''.join('.' if not v else str(v) for v in row) for row in grid)+'\n')
        entries=[]
        for part,(tile,palette,dy) in enumerate(((head,'head',0),(body,'body',8))):
            char=n*4+part*2;tx=(char%16)*8
            for y,row in enumerate(tile):sheet[y][tx:tx+16]=row
            entries.append(dict(char=char,x=0,y=dy,size=16,palette=palette))
        frames[name]=dict(canvas=[16,24],oam=entries,opaque_pixels=sum(bool(v) for row in grid for v in row))
        previews[name]=result
    raw=sheet_codec.grid_to_sheet(sheet)
    assert sheet_codec.sheet_to_grid(raw)==sheet
    text=sheet_codec.grid_to_text(sheet);assert sheet_codec.text_to_grid(text)==sheet
    (out/'protector-sheet.txt').write_text(text)
    (out/'protector-sheet.3bpp').write_bytes(raw)
    save_grid(sheet,out/'protector-sheet-indices.png',HEAD)
    for name,pal in (('head',HEAD),('body',BODY)):
        (out/f'{name}.pal').write_bytes(b''.join(w.to_bytes(2,'little') for w in pal+[0]*8))
    # Exact original human Link pixels, copied from the local vanilla catalog.
    link=Image.open(args.link_reference).convert('RGBA');bg=link.getpixel((0,0))
    link=link.crop((0,0,24,28))
    for y in range(link.height):
        for x in range(link.width):
            if link.getpixel((x,y))==bg:link.putpixel((x,y),(0,0,0,0))
    box=link.getbbox();assert box;link=link.crop(box)
    link.save(out/'vanilla-link-reference.png')
    board=Image.new('RGB',(1030,630),'#242a2c');draw=ImageDraw.Draw(board)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',22)
    small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
    draw.text((24,16),'River protector — native indexed frames',font=font,fill='white')
    draw.text((24,52),'16 x 24 canvas | two OBJ pieces | two seven-colour palettes | no ROM binding',font=small,fill='#c0ccc7')
    for x,name in ((240,'front'),(460,'side')):
        im=previews[name];draw.text((x,96),name.title(),font=font,fill='white')
        board.paste(im.resize((128,192),Image.Resampling.NEAREST),(x,138),im.resize((128,192),Image.Resampling.NEAREST))
        board.paste(im,(x+54,378),im)
    draw.text((24,96),'Vanilla Link',font=font,fill='white')
    enlarged=link.resize((link.width*8,link.height*8),Image.Resampling.NEAREST)
    board.paste(enlarged,(24,330-enlarged.height),enlarged)
    board.paste(link,(80,402-link.height),link)
    draw.text((650,96),'Actual Zora Link source heads',font=font,fill='white')
    heads=Image.open(out.parent.parent/'zora-link-coherence-v1/zora-link-current-source.png').convert('RGBA').crop((0,0,64,16))
    heads=heads.resize((320,80),Image.Resampling.NEAREST);board.paste(heads,(650,153),heads)
    draw.text((650,250),'Original player pixels and palette.',font=small,fill='#c0ccc7')
    draw.text((650,277),'Head-source fragments; no invented pose.',font=small,fill='#c0ccc7')
    draw.text((24,430),'Head',font=small,fill='white');draw.text((24,505),'Body',font=small,fill='white')
    for row,pal in enumerate((HEAD,BODY)):
        for i,w in enumerate(pal[1:],1):
            x=100+(i-1)*75;y=430+row*75
            draw.rectangle((x,y,x+45,y+25),fill=rgb(w));draw.text((x,y+30),f'{w:04X}',font=small,fill='white')
    draw.text((650,430),'Slot 5: yellow fins / brown strap.',font=small,fill='#c0ccc7')
    draw.text((650,457),'Shared scale, cream and muzzle colours.',font=small,fill='#c0ccc7')
    draw.text((24,599),'Native file preview only. Palette-row residency, animation and gameplay are not qualified.',font=small,fill='#c0ccc7')
    board.save(out/'native-frame-preview.png')
    report=dict(status='NATIVE_FILES_REVIEW_ONLY',concept_sha256=CONCEPT_SHA,frames=frames,
                palettes=dict(head=[f'{w:04X}' for w in HEAD],body=[f'{w:04X}' for w in BODY]),
                palette_rows_assigned=False,global_sheets_assigned=False,unique_obj_cells=4,unique_8x8_tiles=16,
                sheet_bytes=len(raw),sheet_roundtrip=True,text_roundtrip=True,composition_matches_trace=True,
                actual_player_sha256=PLAYER_SHA,player_unchanged=True,rom_written=False)
    (out/'RECEIPT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
