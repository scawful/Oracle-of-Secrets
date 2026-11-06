#!/usr/bin/env python3
"""Actual-player palette / mouth preview. Writes fresh candidates, never inputs."""
from pathlib import Path
import argparse, ast, hashlib, json, re
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
SOURCE_SHA='43f78dd7593a25111dfb5d6ba37b2981ccf03741a100cb8cab7dfafe56c51085'

def encode(indices):
    pixels=indices.load();out=bytearray(0x7000)
    for n in range(len(out)//32):
        tx,ty=(n%16)*8,(n//16)*8
        for y in range(8):
            for bit in range(4):
                out[n*32+y*2+bit%2+(16 if bit>=2 else 0)]=sum(((pixels[tx+x,ty+y]>>bit)&1)<<(7-x) for x in range(8))
    return bytes(out)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--renderer',type=Path,required=True)
    ap.add_argument('--main-heads',action='store_true',help='Extend the approved mouth to the main side/open/closed head strip')
    ap.add_argument('--matched-heads',action='store_true',help='Also extend exact mouth motifs through verified head-table buffers')
    ap.add_argument('--head-table-rom',type=Path)
    ap.add_argument('--disassembly',type=Path)
    args=ap.parse_args();out=args.output
    assert not args.matched_heads or (args.main_heads and args.head_table_rom and args.disassembly), 'matched heads require main heads and verified table inputs'
    assert not out.exists(),'fresh output required'
    # Reuse the established palette proof's decoder/renderer only, without its I/O.
    tree=ast.parse(args.renderer.read_text());ns={'Image':Image}
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('rgb','decode','paint')],type_ignores=[]),'existing indexed render helpers','exec'),ns)
    path=ROOT/'Masks/gfx/zora_link.4bpp';source=path.read_bytes();assert hashlib.sha256(source).hexdigest()==SOURCE_SHA
    text=(ROOT/'Masks/zora_mask.asm').read_text();section=text.split('zora_palette:',1)[1].split('; dw',1)[0]
    current=[int(w,16) for w in re.findall(r'\$([0-9A-Fa-f]{4})',section)];assert len(current)==16
    proposal=current.copy()
    # Same colour words as the protector native head/body palette. Existing
    # white eyes (1) and yellow fins (2) remain untouched.
    for i,w in {5:0x0C63,6:0x46F0,7:0x39E5,10:0x5B7D,11:0x2525,12:0x46F0,13:0x1ADF}.items():proposal[i]=w
    indices=ns['decode'](source);assert encode(indices)==source
    rows=[];offsets=[]
    if args.head_table_rom or args.disassembly:
        assert args.head_table_rom and args.disassembly, 'both head-table inputs required'
        asm=args.disassembly.read_text()
        section=asm.split('LinkOAM_HeadAddresses:',1)[1].split('LinkOAM_BodyAddresses:',1)[0]
        rows=[(int(a,16),int(v,16)) for a,v in re.findall(r'#_([0-9A-F]{6}): dw LinkGraphics\+\$([0-9A-F]{4})',section)]
        assert len(rows)==303, 'unexpected head-table shape'
        rom=args.head_table_rom.read_bytes()
        for address,offset in rows:
            pc=((address>>16)&127)*0x8000+(address&0x7fff)
            assert int.from_bytes(rom[pc:pc+2],'little')==0x8000+offset, 'head lookup changed'
        offsets=sorted({v for _,v in rows})
    def source_xy(offset,x,y):
        tile=(offset+(y//8)*0x200+(x//8)*32)//32
        return ((tile%16)*8+x%8,(tile//16)*8+y%8)
    def head_view(data,offset):
        decoded=ns['decode'](data);frame=Image.new('P',(16,16))
        for y in range(16):
            for x in range(16):frame.putpixel((x,y),decoded.getpixel(source_xy(offset,x,y)))
        return frame
    mouth=indices.copy();changes=[]
    # Two existing frontal head-source groups. Keep teeth/white, dark outlines,
    # eyes and yellow fins exact. Only muzzle scale pixels become amber/brown.
    regions=[dict(origin=16,x0=4,x1=12,y0=10,y1=15,name='front-closed'),
             dict(origin=48,x0=4,x1=12,y0=10,y1=15,name='front-open')]
    if args.main_heads:
        regions += [dict(origin=0,x0=10,x1=16,y0=9,y1=14,name='side'),
                    dict(origin=64,x0=4,x1=12,y0=10,y1=15,name='front-closed-copy'),
                    dict(origin=80,x0=4,x1=12,y0=5,y1=14,name='wide-open'),
                    dict(origin=96,x0=4,x1=12,y0=9,y1=14,name='blink'),
                    dict(origin=112,x0=4,x1=12,y0=6,y1=14,name='wide-open-alt')]
    for region in regions:
        for y in range(region['y0'],region['y1']):
            for x in range(region['origin']+region['x0'],region['origin']+region['x1']):
                old=indices.getpixel((x,y))
                if old not in (6,7):continue
                new=13 if old==6 else 14
                mouth.putpixel((x,y),new);changes.append(dict(x=x,y=y,before=old,after=new))
    matched=[]
    if args.matched_heads:
        # Match the complete bounded muzzle motif, preserving every non-scale
        # index. Normalization admits only the two existing scale shades (6/7).
        def normalized(values):return tuple(6 if v==7 else v for v in values)
        templates=[]
        for region in regions:
            w=region['x1']-region['x0'];h=region['y1']-region['y0']
            frame=head_view(source,region['origin']//8*32)
            pattern=normalized(frame.crop((region['x0'],region['y0'],region['x1'],region['y1'])).get_flattened_data())
            templates.append((region['name'],w,h,pattern))
        change_map={(c['x'],c['y']):c for c in changes}
        for offset in offsets:
            frame=head_view(source,offset)
            for name,w,h,pattern in templates:
                for y in range(17-h):
                    for x in range(17-w):
                        if normalized(frame.crop((x,y,x+w,y+h)).get_flattened_data())!=pattern:continue
                        matched.append(dict(buffer=f'{offset:04X}',template=name,x=x,y=y))
                        for yy in range(y,y+h):
                            for xx in range(x,x+w):
                                sx,sy=source_xy(offset,xx,yy);old=indices.getpixel((sx,sy))
                                if old not in (6,7):continue
                                new=13 if old==6 else 14
                                mouth.putpixel((sx,sy),new)
                                change_map[sx,sy]=dict(x=sx,y=sy,before=old,after=new)
        changes=sorted(change_map.values(),key=lambda c:(c['y'],c['x']))
    assert changes
    diff=[(x,y) for y in range(448) for x in range(128) if indices.getpixel((x,y))!=mouth.getpixel((x,y))]
    assert set(diff)=={(c['x'],c['y']) for c in changes}
    assert all(c['before'] in (6,7) and c['after'] in (13,14) for c in changes)
    if not args.matched_heads:
        assert all(c['y']<16 for c in changes), 'only the primary head strip may change'
        assert all(indices.getpixel((x,y))==mouth.getpixel((x,y)) for y in range(16,448) for x in range(128))
    assert all((a==v) if a in (1,2,5) else True for a,v in zip(indices.get_flattened_data(),mouth.get_flattened_data())), 'eyes/fins/outlines must retain their indices'
    # Preserve the approved two frontal regions exactly when extending variants.
    if args.main_heads:
        accepted=indices.copy()
        for origin in (16,48):
            for y in range(10,15):
                for x in range(origin+4,origin+12):
                    v=indices.getpixel((x,y))
                    if v in (6,7):accepted.putpixel((x,y),13 if v==6 else 14)
        for origin in (16,48):
            assert list(mouth.crop((origin,0,origin+16,16)).get_flattened_data())==list(accepted.crop((origin,0,origin+16,16)).get_flattened_data())
    packed=encode(mouth);assert list(ns['decode'](packed).get_flattened_data())==list(mouth.get_flattened_data())
    images=[ns['paint'](indices,current),ns['paint'](indices,proposal),ns['paint'](mouth,proposal)]
    out.mkdir(parents=True)
    for name,im in zip(('current','protector-palette','protector-palette-mouth-draft'),images):im.save(out/(name+'.png'))
    (out/'zora-link-mouth-draft.4bpp').write_bytes(packed)
    (out/'palette-proposal.asm').write_text('; Preview only; no org, no source include.\n'+'\n'.join('dw '+', '.join(f'${w:04X}' for w in proposal[i:i+8]) for i in (0,8))+'\n')
    board=Image.new('RGB',(1440,730),'#242a2c');draw=ImageDraw.Draw(board)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',22)
    small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17)
    draw.text((24,16),'ACTUAL ZORA LINK — protector palette and mouth draft',font=font,fill='white')
    for col,(im,label) in enumerate(zip(images,('Current source','Protector palette only','Same palette + mouth draft'))):
        x=24+col*472;draw.text((x,65),label,font=font,fill='white')
        head_width=128 if args.main_heads else 64
        head_scale=3 if args.main_heads else 6
        for rect,pos,scale in (((0,0,head_width,16),(x,112),head_scale),((0,64,128,112),(x,415),3)):
            cut=im.crop(rect);cut=cut.resize((cut.width*scale,cut.height*scale),Image.Resampling.NEAREST);board.paste(cut,pos,cut)
        # Real front-head source group, enlarged for an inspectable mouth change.
        cut=im.crop((16,0,32,16)).resize((144,144),Image.Resampling.NEAREST);board.paste(cut,(x,243),cut)
        draw.text((x,575),'Head / body source fragments',font=small,fill='#c4cfc9')
    scope=f"{len(set(m['buffer'] for m in matched))} matched head buffers" if args.matched_heads else f'{len(regions)} head groups'
    draw.text((24,622),f'Mouth treatment: {len(changes)} source pixels changed, across {scope}.',font=small,fill='white')
    draw.text((24,650),'Eyes, yellow fins and outlines are exact; every pixel outside the verified mouth masks retains its index.',font=small,fill='white')
    draw.text((24,690),'Preview candidates only. No ROM write, source replacement, invented player anatomy or native pose claim.',font=small,fill='#c4cfc9')
    board.save(out/'face-comparison.png')
    report=dict(status='PREVIEW_ONLY_NOT_ADOPTED',source_sha256=SOURCE_SHA,
                source_palette_sha256=hashlib.sha256(text.encode()).hexdigest(),
                palette_before=[f'{w:04X}' for w in current],palette_proposed=[f'{w:04X}' for w in proposal],
                palette_changed_indices=[i for i in range(16) if current[i]!=proposal[i]],
                mouth_pixel_changes=changes,mouth_regions=regions,matched_head_motifs=matched,changed_graphic_pixels=len(changes),all_other_indices_exact=True,
                four_bpp_roundtrip=True,source_unchanged=path.read_bytes()==source,rom_written=False,native_pose_verified=False)
    if offsets:
        audit=Image.new('RGB',(1100,((len(offsets)+7)//8)*124+80),'#242a2c');ad=ImageDraw.Draw(audit)
        ad.text((20,12),'Actual head buffers from verified animation addresses: current / amber candidate',font=small,fill='white')
        views=[]
        for i,offset in enumerate(offsets):
            x=20+(i%8)*136;y=50+(i//8)*124
            old=head_view(source,offset);new=head_view(packed,offset)
            a=ns['paint'](old,current).resize((48,48),Image.Resampling.NEAREST)
            b=ns['paint'](new,proposal).resize((48,48),Image.Resampling.NEAREST)
            audit.paste(a,(x,y),a);audit.paste(b,(x+54,y),b)
            changed=sum(a!=b for a,b in zip(old.get_flattened_data(),new.get_flattened_data()))
            ad.text((x,y+55),f'${offset:04X}',font=small,fill='white')
            ad.text((x,y+80),f'{changed} px',font=small,fill='#c4cfc9')
            views.append(dict(offset=f'{offset:04X}',changed_indices=changed))
        audit.save(out/'all-head-buffers.png')
        report['head_table_audit']=dict(table_entries=len(rows),unique_buffers=len(offsets),all_entries_match_rom=True,views=views,
            note='Only main-strip mouth masks and complete matched motifs are edited. Unmatched special views retain original indices; runtime pose coverage remains open.')
    (out/'RECEIPT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','palette_changed_indices','changed_graphic_pixels','four_bpp_roundtrip','source_unchanged','rom_written')},indent=2))

if __name__=='__main__':main()
