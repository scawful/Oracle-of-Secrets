#!/usr/bin/env python3
"""Native side/rear charge and slam candidates; no binding or ROM writer.

Reclaims unused rigid-front cells, preserving every approved gait/slam/NPC
render. Side gets a native articulated rig; right uses hardware X-flip.
"""
from pathlib import Path
import argparse,copy,hashlib,json
from PIL import Image,ImageDraw,ImageFont
import warden_walk_preview as walk
slam=walk.slam
pack=walk.pack

ARM_BOUNDS={23:(14,18),24:(14,18),25:(13,17),26:(12,16),27:(11,15),28:(10,14),29:(9,13),30:(7,13),31:(7,13)}
SLAM_KEYS=('windup','held','strike','stuck','recover')
CHARGE_KEYS=('brace','stride_a','stride_b','brake')
SIDE_POSES={
 'windup':dict(angle=90,pivot=(17,23),head=(2,-1),chest=(2,0),tank=(3,0),hips=(1,1)),
 'held':dict(angle=180,pivot=(18,21),head=(1,-3),chest=(0,-2),tank=(1,-2),hips=(0,0)),
 'strike':dict(angle=0,pivot=(13,24),head=(-3,2),chest=(-2,2),tank=(-1,1),hips=(1,1)),
 'stuck':dict(angle=0,pivot=(14,24),head=(-2,2),chest=(-1,2),tank=(0,1),hips=(1,1),anchor=(7,31)),
 'recover':dict(angle=0,pivot=(16,22),head=(1,-1),chest=(1,0),tank=(2,0),hips=(0,0)),
 'brace':dict(angle=0,pivot=(17,23),head=(2,0),chest=(1,0),tank=(2,0),hips=(0,0)),
 'stride_a':dict(angle=0,pivot=(14,24),head=(-3,1),chest=(-2,1),tank=(-1,0),hips=(1,0)),
 'stride_b':dict(angle=0,pivot=(14,23),head=(-3,0),chest=(-2,0),tank=(-1,-1),hips=(1,0)),
 'brake':dict(angle=0,pivot=(16,24),head=(1,2),chest=(0,1),tank=(1,1),hips=(0,1)),
}

def side_parts(grid):
    groups={};arm=[];changes=[];removed=[]
    for y,row in enumerate(grid):
        for x,value in enumerate(row):
            if not value:continue
            if y in ARM_BOUNDS and ARM_BOUNDS[y][0]<=x<=ARM_BOUNDS[y][1]:
                arm.append((x,y,1 if value in (8,9) else value));removed.append([x,y]);continue
            if y>=32 and x<16 and not (x>=13 and y<=36 and value in (1,2,3,4,5,6,7)):
                removed.append([x,y]);continue
            if (y<=16 and x<=18) or (17<=y<=20 and x<=11):name='head'
            elif y<=17 and x>=19:name='hose'
            elif x>=22 and y<=29:name='tank'
            elif y>=35 and x>=16:name='leg'
            elif y>=28:name='hips'
            else:name='chest'
            v=value
            if name in ('head','chest','tank','hips') and v in (8,9):
                v=1 if v==8 else 2;changes.append(dict(x=x,y=y,before=value,after=v,part=name))
            groups.setdefault(name,[]).append((x,y,v))
    # Raising the forearm reveals armour that the side source never painted.
    # Author its dark bronze underside only inside the removed arm corridor.
    # The native forearm remains the foreground layer in the resting poses.
    underarm=[]
    for y,(left,right) in ARM_BOUNDS.items():
        edge=14 if y<=27 else 13
        for x in range(max(edge,left),right+1):
            v=1 if x==edge else 2 if x==edge+1 else 4 if x==17 and y<=25 else 3
            groups['chest' if y<=27 else 'hips'].append((x,y,v));underarm.append([x,y,v])
    # Existing lower breastplate/belt pixels overlap the hip joint, keeping
    # the stretched overhead pose connected without inventing a torso patch.
    groups['hips'].extend((x,y,v) for x,y,v in groups['chest'] if 25<=y<=28)
    pieces=[]
    for name in ('head','chest','hips','leg','tank','hose'):
        points=groups[name];x0=min(x for x,y,v in points);y0=min(y for x,y,v in points)
        assert max(x for x,y,v in points)-x0<16 and max(y for x,y,v in points)-y0<16,(name,x0,y0)
        for palette in ('warden_armor','warden_iron'):
            tile=[[0]*16 for _ in range(16)]
            for x,y,v in points:
                if palette=='warden_armor' and v<=7:tile[y-y0][x-x0]=v
                elif palette=='warden_iron' and v in (8,9):tile[y-y0][x-x0]=v-6
            if any(v for row in tile for v in row):pieces.append(dict(part=name,x=x0,y=y0,palette=palette,tile=tile))
    return pieces,arm,changes,removed,underarm

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('walk-pack','body-pack','base-pack','accepted','output'):ap.add_argument('--'+n,type=Path,required=True)
    args=ap.parse_args();out=args.output;assert not out.exists()
    w=json.loads((args.walk_pack/'RECEIPT.json').read_text());b=json.loads((args.body_pack/'RECEIPT.json').read_text());base=json.loads((args.base_pack/'RECEIPT.json').read_text())
    pages=[pack.sheet_codec.sheet_to_grid((args.walk_pack/f'actor-page-{i}.3bpp').read_bytes()) for i in range(4)]
    used={e['char'] for f in w['frames'].values() for e in f['oam']}|{e['char'] for f in b['frames'].values() for e in f['oam']}
    used|={e['char'] for n,f in base['frames'].items() if n.startswith('protector') for e in f['oam']}
    retired={e['char'] for e in base['frames']['warden_idle_front']['oam']}-used
    assert len(used)==42 and len(retired)==12
    allocated={bytes(v for row in walk.tile_at(pages,c) for v in row):c for c in used}
    cells=[q+r+x for q in (0,0x40,0x80,0xC0) for r in (0,0x20) for x in range(0,16,2) if q+r+x not in used|pack.RESERVED];added=[]
    def alloc(piece):
        tile=piece['tile'];key=bytes(v for row in tile for v in row);assert all(v<=7 for v in key)
        if key not in allocated:
            assert len(added)<len(cells),'directional attack pack exceeds room atlas'
            c=cells[len(added)];added.append(c);allocated[key]=c;tx,ty=(c&15)*8,((c&63)//16)*8
            for y,row in enumerate(tile):pages[c>>6][ty+y][tx:tx+16]=row
        return dict(char=allocated[key],x=piece['x'],y=piece['y'],palette=piece['palette'],part=piece.get('part',''))
    side_grid=[[0 if c=='.' else int(c) for c in row] for row in (args.accepted/'warden_idle_side-roles.txt').read_text().splitlines()]
    side,arm,changes,removed,underarm=side_parts(side_grid)
    anchor=[(x,y,int(c)) for y,row in enumerate(slam.ANCHOR) for x,c in enumerate(row) if c!='.']
    front_body=[[0 if c=='.' else int(c) for c in row] for row in (args.accepted/'warden_idle_front-roles.txt').read_text().splitlines()]
    for y,row in enumerate(front_body):
        for x,v in enumerate(row):
            if (22<=y<=31 and x<=8) or (32<=y<=43 and x<=5):row[x]=0
    front_parts,_,_=slam.articulated_body(front_body)
    rear_idle=w['frames']['rear_0']['oam'];rear_head=next(e['char'] for e in rear_idle if e['part']=='head');rear_tank=next(e['char'] for e in rear_idle if e['part']=='back_tank')
    frames={};images={}
    for name,p in SIDE_POSES.items():
        px,py=p['pivot'];dx,dy=slam.rotate(11-17,30-23,p['angle']);grip=(px+dx,py+dy);ag=p.get('anchor',grip)
        a=slam.component(arm,(17,23),p['angle'],p['pivot'],'warden_armor');a['part']='weapon_arm'
        h=slam.component(anchor,(7,3),p['angle'],ag,'warden_iron');h['part']='anchor'
        pieces=[h,a]
        for original in side:
            e=copy.deepcopy(original);part=e['part'];offset=p['tank'] if part in ('tank','hose') else p['hips'] if part=='hips' else (0,0) if part=='leg' else p[part]
            e['x']+=offset[0];e['y']+=offset[1]
            if part=='leg':
                e['x']+=-1 if name in ('strike','stuck','stride_a') else 1
                if name=='stride_b':e['y']-=1
            pieces.append(e)
        # Existing accepted rear boot behind the body, no additional artwork.
        for e in w['frames']['left_0']['oam']:
            if e.get('part')=='rear_leg':
                e=copy.deepcopy(e);e['x']+=1 if name in ('strike','stuck') else -1
                if name=='stride_a':e['y']-=1
                pieces.append(dict(e,tile=walk.tile_at(pages,e['char'])))
        entries=[alloc(e) for e in pieces]
        action='slam' if name in SLAM_KEYS else 'charge'
        frames[f'left_{action}_{name}']=entries;frames[f'right_{action}_{name}']=walk.mirror(entries)
    for name,front in b['frames'].items():
        entries=copy.deepcopy(front['oam']);parts=[dict(e,part=p['name']) for e,p in zip(entries[2:],front_parts)]
        # Keep the bronze waist behind the foreground tank; dropping both
        # chest palette layers exposed a one-pixel torso/hip gap on extension.
        rear=entries[:2]+[e for e in parts if e['part']!='chest' or e['palette']=='warden_armor']
        for e in rear:
            if e.get('part')=='head':e['char']=rear_head
        dx,dy=slam.BODY_OFFSETS[name]['chest']
        rear=[dict(char=rear_tank,x=8+dx,y=13+dy,palette='warden_iron',part='back_tank')]+rear
        frames[f'rear_slam_{name}']=walk.mirror(rear)
    for i,name in enumerate(CHARGE_KEYS):
        entries=copy.deepcopy(w['frames'][f'rear_{i}']['oam'])
        for e in entries:
            part=e.get('part')
            if part=='head':e['y']+=1 if name=='brace' else 2
            elif part in ('back_tank','left_shoulder','right_shoulder','tank','chest'):
                e['y']+=-1 if name.startswith('stride') else 1 if name=='brake' else 0
        frames[f'rear_charge_{name}']=entries
    for name,entries in frames.items():images[name]=walk.render(entries,pages)
    for action,keys in (('slam',SLAM_KEYS),('charge',CHARGE_KEYS)):
        for key in keys:assert images[f'right_{action}_{key}'].tobytes()==images[f'left_{action}_{key}'].transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes()
    free_cells=sorted(set(cells)-set(added))
    for c in free_cells:
        tx,ty=(c&15)*8,((c&63)//16)*8
        for y in range(16):pages[c>>6][ty+y][tx:tx+16]=[0]*16
    for c in used|{0xC0,0xC2,0xE0,0xE2}:
        old=[pack.sheet_codec.sheet_to_grid((args.walk_pack/f'actor-page-{i}.3bpp').read_bytes()) for i in range(4)]
        assert walk.tile_at(old,c)==walk.tile_at(pages,c)
    out.mkdir(parents=True)
    for i,page in enumerate(pages):
        raw=pack.sheet_codec.grid_to_sheet(page);assert pack.sheet_codec.sheet_to_grid(raw)==page
        stream=pack.lz2.compress(raw);assert pack.lz2.decompress(stream,max_output=1536)==(raw,len(stream))
        (out/f'actor-page-{i}.3bpp').write_bytes(raw);(out/f'actor-page-{i}.txt').write_text(pack.sheet_codec.grid_to_text(page));(out/f'actor-page-{i}.lz2').write_bytes(stream)
    for n,im in images.items():im.save(out/(n+'-native.png'))
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',22);small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
    for action,keys in (('slam',SLAM_KEYS),('charge',CHARGE_KEYS)):
        board=Image.new('RGB',(1480,820),'#252a2d');d=ImageDraw.Draw(board)
        d.text((24,15),'Warden '+action+' — side and rear native frame study',font=font,fill='white')
        d.text((24,50),'Left-facing side + rear shown; right-facing frames are exact mirrored OAM. Private ROM unchanged.',font=small,fill='#c7d1ca')
        for row,direction in enumerate(('left','rear')):
            y=90+row*340;d.text((24,y),direction.title(),font=font,fill='white')
            for col,key in enumerate(keys):
                x=24+col*290;d.text((x,y+34),key.replace('_',' '),font=small,fill='white')
                im=images[f'{direction}_{action}_{key}'].resize((256,256),Image.Resampling.NEAREST);board.paste(im,(x,y+60),im)
        total=len(used)+len(added)
        d.text((24,780),f'Combined approved art + directional attacks: {total}/58 cells; {58-total} free. Preview only.',font=small,fill='#c7d1ca');board.save(out/(action+'-directional-sheet.png'))
        loop=[];durations=[200,460,60,660,260] if action=='slam' else [660,130,130,600]
        for key in keys:
            frame=Image.new('RGB',(960,400),'#252a2d');fd=ImageDraw.Draw(frame)
            for x,direction in ((0,'left'),(480,'rear')):
                fd.text((x+20,15),direction.title()+' '+action+' — '+key.replace('_',' '),font=small,fill='white')
                im=images[f'{direction}_{action}_{key}'].resize((256,256),Image.Resampling.NEAREST);frame.paste(im,(x+100,70),im)
                fd.line((x+20,310,x+460,310),fill='#63756b')
            fd.text((20,360),'Native pose timing study; no movement, hitboxes or attack logic installed.',font=small,fill='#c7d1ca');loop.append(frame)
        loop[0].save(out/(action+'-directional-motion.gif'),save_all=True,append_images=loop[1:],duration=durations,loop=0,optimize=False)
    result=dict(status='NATIVE_DIRECTIONAL_ATTACK_PREVIEW_ONLY',baseline_approved_cells=len(used),retired_unused_rigid_front_cells=[f'{c:02X}' for c in sorted(retired)],added_cells=[f'{c:02X}' for c in added],total_cells=len(used)+len(added),capacity=58,free_cells=58-len(used)-len(added),free_cell_indices=[f'{c:02X}' for c in free_cells],
                side_accent_changes=changes,side_arm_and_old_weapon_mask=removed,side_revealed_underarm_armor=underarm,
                frames={n:dict(oam=e,peak_scanline_objects=max(sum(p['y']<=y<p['y']+16 for p in e) for y in range(-16,48))) for n,e in frames.items()},
                approved_art_cells_exact=True,princess_cells_exact=True,baby_slots_reserved=True,right_mirror_exact=True,rom_written=False,source_binding_installed=False,native_runtime_qualified=False)
    (out/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('status','baseline_approved_cells','added_cells','total_cells','free_cells','rom_written')},indent=2))

if __name__=='__main__':main()
