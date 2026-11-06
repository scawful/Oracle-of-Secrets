#!/usr/bin/env python3
"""Preview native four-facing warden gait; rear artwork is a new review draft.

Reuses accepted articulated-slam and side graphics. Emits candidates only,
with explicit hardware X-flip geometry; never updates source binding or ROM.
"""
from pathlib import Path
import argparse, copy, hashlib, json
from PIL import Image, ImageDraw, ImageFont
import warden_anchor_slam_preview as slam
pack=slam.pack

TANK=(
    '.....111111.....','....12233221....','...1233333321...',
    '..123333333321..','..145555555541..',
    '..146666666641..','..145555555541..','..123333333321..',
    '..123332333321..','..123332333321..','..145555555541..',
    '..146666666641..','..145555555541..','..123333333321..',
    '...1233333321...','....11111111....',
)

def tile_at(pages,char):
    tx,ty=(char&15)*8,((char&63)//16)*8
    return [r[tx:tx+16] for r in pages[char>>6][ty:ty+16]]

def render(entries,pages):
    im=Image.new('RGBA',(64,64))
    for e in reversed(entries):
        tile=tile_at(pages,e['char']);pal=pack.PALETTES[e['palette']]
        for y in range(16):
            for x in range(16):
                v=tile[y][15-x if e.get('flip_x') else x]
                if v:
                    px,py=e['x']+x+16,e['y']+y+16
                    assert 0<=px<64 and 0<=py<64
                    im.putpixel((px,py),pack.rgb(pal[v])+(255,))
    return im

def mirror(entries):
    return [dict(e,x=32-e['x']-16,flip_x=not e.get('flip_x',False)) for e in entries]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('body-pack','base-pack','accepted','output'):ap.add_argument('--'+n,type=Path,required=True)
    args=ap.parse_args();out=args.output;assert not out.exists()
    report=json.loads((args.body_pack/'RECEIPT.json').read_text());base=json.loads((args.base_pack/'RECEIPT.json').read_text())
    assert report['total_obj_cells']==50 and report['articulated_body']
    pages=[pack.sheet_codec.sheet_to_grid((args.body_pack/f'actor-page-{i}.3bpp').read_bytes()) for i in range(4)]
    protected={e['char'] for n,f in base['frames'].items() if n not in report['retired_legacy_frame_cells'] for e in f['oam']}
    protected.update(e['char'] for f in report['frames'].values() for e in f['oam'])
    assert len(protected)==50
    allocated={bytes(v for r in tile_at(pages,c) for v in r):c for c in protected}
    free=[q+r+x for q in (0,0x40,0x80,0xC0) for r in (0,0x20) for x in range(0,16,2) if q+r+x not in protected|pack.RESERVED]
    added=[]
    def allocate(tile):
        key=bytes(v for r in tile for v in r);assert all(v<=7 for v in key)
        if key not in allocated:
            assert len(added)<len(free),'movement views exceed room graphics capacity'
            c=free[len(added)];added.append(c);allocated[key]=c
            tx,ty=(c&15)*8,((c&63)//16)*8
            for y,r in enumerate(tile):pages[c>>6][ty+y][tx:tx+16]=r
        return allocated[key]
    # Recover is angle-zero, so subtract its offsets to recover neutral OAM.
    front=[[0 if c=='.' else int(c) for c in row] for row in (args.accepted/'warden_idle_front-roles.txt').read_text().splitlines()]
    body=[r.copy() for r in front]
    for y,row in enumerate(body):
        for x,v in enumerate(row):
            if (22<=y<=31 and x<=8) or (32<=y<=43 and x<=5):row[x]=0
    parts,_,_=slam.articulated_body(body)
    neutral=copy.deepcopy(report['frames']['recover']['oam'])
    neutral[0]['y']+=2;neutral[1]['y']+=2
    neutral[0]['part']='anchor';neutral[1]['part']='weapon_arm'
    assert len(neutral)==len(parts)+2
    for e,piece in zip(neutral[2:],parts):
        name=piece['name'];dx,dy=slam.BODY_OFFSETS['recover'][name];e['x']-=dx;e['y']-=dy;e['part']=name
    head=next(e for e in neutral if e['part']=='head')
    source=tile_at(pages,head['char']);rear_head=[[0]*16 for _ in range(16)]
    for y,row in enumerate(source):
        xs=[x for x,v in enumerate(row) if v]
        if not xs:continue
        left,right=min(xs),max(xs)
        for x in range(left,right+1):
            rear_head[y][x]=1 if x in (left,right) or right-left<=2 else 5 if x in (left+1,right-1) else 6
    for y in range(3,9):
        if rear_head[y][6] not in (0,1):rear_head[y][6]=5
    # Rear skull ends above the collar. Filling the original front jaw/neck
    # silhouette made a tall pale column rather than a separate skull.
    for y,left,right in ((9,2,9),(10,3,8),(11,4,7),(12,4,7)):
        rear_head[y]=[0]*16
        for x in range(left,right+1):rear_head[y][x]=1 if x in (left,right) else 5 if y>=11 else 6
    rear_char=allocate(rear_head)
    assert len(TANK)==16
    tank=[[0]*16 for _ in range(16)]
    for y,row in enumerate(TANK):
        assert len(row)==16
        tank[y]=[0 if c=='.' else int(c) for c in row]
    tank_chars=[allocate(tank)]
    side_grid=[[0 if c=='.' else int(c) for c in row] for row in (args.accepted/'warden_idle_side-roles.txt').read_text().splitlines()]
    rear_leg=[]
    for palette in ('warden_armor','warden_iron'):
        tile=[[0]*16 for _ in range(16)]
        for y in range(35,44):
            for x in range(16,25):
                v=side_grid[y][x]
                if palette=='warden_armor' and 1<=v<=7:tile[y-35][x-16]=v
                elif palette=='warden_iron' and v in (8,9):tile[y-35][x-16]=v-6
        if any(v for row in tile for v in row):rear_leg.append(dict(char=allocate(tile),x=16,y=35,palette=palette,part='rear_leg'))
    frames={};images={}
    # Four gait keys. Front and rear share the same planted leg rig; side
    # exposes the copied rear boot behind the existing foreground boot.
    gaits=((0,-1,0,1),(1,0,-1,-1),(0,1,0,-1),(1,0,-1,1))
    for phase,(bob,left_x,left_y,right_x) in enumerate(gaits):
        entries=copy.deepcopy(neutral)
        for e in entries:
            name=e['part']
            if name=='left_leg':e['x']+=left_x;e['y']+=left_y
            elif name=='right_leg':e['x']+=right_x;e['y']+=-1 if phase==3 else 0
            elif name=='hips':e['y']-=bob
            elif name in ('anchor','weapon_arm'):e['y']-=bob
            else:e['y']-=bob;e['x']+=1 if phase<2 else -1
        frames[f'front_{phase}']=entries
        rear=[]
        for e in entries:
            if e['part']=='chest':continue
            e=dict(e)
            if e['part']=='head':e['char']=rear_char
            rear.append(e)
        rear.extend(dict(char=c,x=8,y=16+i*16-bob,palette='warden_iron',part='back_tank') for i,c in enumerate(tank_chars))
        frames[f'rear_{phase}']=mirror(rear)
        side=copy.deepcopy(base['frames']['warden_idle_side']['oam'])
        for e in side:
            e['part']='side_base'
            if e['y']<32:e['y']-=bob
            elif e['x']==16:e['x']+=-1 if phase in (1,2) else 1;e['y']+=-1 if phase==1 else 0
        for e in rear_leg:
            e=dict(e);e['x']+=3 if phase in (0,1) else 1;e['y']+=-2 if phase==2 else -1 if phase==0 else 0;side.append(e)
        frames[f'left_{phase}']=side;frames[f'right_{phase}']=mirror(side)
    for n,entries in frames.items():images[n]=render(entries,pages)
    for phase in range(4):
        assert images[f'right_{phase}'].tobytes()==images[f'left_{phase}'].transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes()
    # Check all original cells including protected Princess art exactly.
    for c in protected|{0xC0,0xC2,0xE0,0xE2}:
        old=[pack.sheet_codec.sheet_to_grid((args.body_pack/f'actor-page-{i}.3bpp').read_bytes()) for i in range(4)]
        assert tile_at(old,c)==tile_at(pages,c)
    out.mkdir(parents=True)
    for i,page in enumerate(pages):
        raw=pack.sheet_codec.grid_to_sheet(page);assert pack.sheet_codec.sheet_to_grid(raw)==page
        stream=pack.lz2.compress(raw);assert pack.lz2.decompress(stream,max_output=1536)==(raw,len(stream))
        (out/f'actor-page-{i}.3bpp').write_bytes(raw);(out/f'actor-page-{i}.txt').write_text(pack.sheet_codec.grid_to_text(page));(out/f'actor-page-{i}.lz2').write_bytes(stream)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',22);small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
    board=Image.new('RGB',(1000,1080),'#252a2d');d=ImageDraw.Draw(board)
    d.text((22,15),'Warden gait and facing study — native preview only',font=font,fill='white')
    d.text((22,48),'Front uses accepted rig; side adds a rear boot; right mirrors left. Rear is a new art draft.',font=small,fill='#c7d1ca')
    directions=('front','left','rear','right')
    for row,direction in enumerate(directions):
        y=90+row*230;d.text((22,y),direction.title()+(' — DRAFT' if direction=='rear' else ''),font=small,fill='white')
        for phase in range(4):
            n=f'{direction}_{phase}';im=images[n];im.save(out/(n+'-native.png'));large=im.resize((192,192),Image.Resampling.NEAREST)
            x=90+phase*220;board.paste(large,(x,y+20),large);d.text((x+75,y+207),str(phase+1),font=small,fill='#c7d1ca')
    total=len(protected)+len(added)
    d.text((22,1020),f'All accepted body/slam/protector cells preserved. Combined pack {total}/58; {58-total} free.',font=small,fill='#c7d1ca')
    d.text((22,1050),'Gait key poses only; no movement AI, turn logic or directional attacks installed.',font=small,fill='#c7d1ca');board.save(out/'walk-facing-sheet.png')
    animation=[]
    for phase in range(4):
        b=Image.new('RGB',(960,720),'#252a2d');dr=ImageDraw.Draw(b)
        for (x,y),direction in zip(((0,0),(480,0),(0,360),(480,360)),directions):
            dr.text((x+20,y+12),direction.title()+(' — new rear draft' if direction=='rear' else ''),font=small,fill='white')
            im=images[f'{direction}_{phase}'].resize((256,256),Image.Resampling.NEAREST);b.paste(im,(x+100,y+55),im)
            dr.line((x+20,y+295,x+450,y+295),fill='#63756b')
        animation.append(b)
    animation[0].save(out/'walk-facing-motion.gif',save_all=True,append_images=animation[1:],duration=130,loop=0,optimize=False)
    result=dict(status='NATIVE_GAIT_AND_REAR_DRAFT_ONLY',body_pack_receipt_sha256=hashlib.sha256((args.body_pack/'RECEIPT.json').read_bytes()).hexdigest(),baseline_cells=len(protected),added_cells=[f'{c:02X}' for c in added],total_cells=total,capacity=58,free_cells=58-total,
                frames={n:dict(oam=e,peak_scanline_objects=max(sum(p['y']<=y<p['y']+16 for p in e) for y in range(-16,48))) for n,e in frames.items()},
                old_cells_exact=True,princess_cells_exact=True,baby_slots_reserved=True,right_flip_exact=True,rear_art_accepted=False,
                rom_written=False,source_binding_installed=False,native_runtime_qualified=False)
    (out/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','baseline_cells','added_cells','total_cells','free_cells','rom_written')},indent=2))

if __name__=='__main__':main()
