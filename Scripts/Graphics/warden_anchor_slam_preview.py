#!/usr/bin/env python3
"""Native indexed anchor-slam rig study. Emits preview art/pages, never a ROM.

The default preserves accepted body pixels outside the weapon-arm mask. The
optional articulated variant reuses nine body components, simplifies sparse
joint accents and reclaims the old near-static brace/vent cells. No enlarged-
image resampling, ROM writes or source-binding installation.
"""
from pathlib import Path
import argparse
import hashlib
import json
from PIL import Image, ImageDraw, ImageFont
import d4_actor_native_pack as pack

ANCHOR=(
    '......111.......',
    '.....12221......',
    '.....12.21......',
    '......131.......',
    '...111131111....',
    '...122232221....',
    '......131.......',
    '......131.......',
    '.11...131...11..',
    '.121..131..121..',
    '.1231113111321..',
    '..12322322321...',
    '...123232321....',
    '....1232321.....',
    '.....12321......',
    '......111.......',
)
POSES=(
    dict(name='windup',angle=90,pivot=(6,22),mass=0,frames=12),
    dict(name='held',angle=180,pivot=(4,20),mass=0,frames=28),
    # Keep body tile rows planted. Shifting the upper rows down made a one-line
    # 10-OBJ overlap with the boots; the arm/anchor supply the impact movement.
    dict(name='strike',angle=0,pivot=(8,23),mass=0,frames=4),
    dict(name='stuck',angle=0,pivot=(8,22),mass=0,frames=40,anchor_grip=(6,31)),
    dict(name='recover',angle=0,pivot=(7,21),mass=0,frames=16),
)
BODY_OFFSETS={
    'windup':dict(head=(3,-1),tank=(4,0),left_shoulder=(1,0),right_shoulder=(3,-1),chest=(2,0),hips=(0,1),left_leg=(-2,0),right_leg=(2,0),right_arm=(3,0)),
    'held':dict(head=(1,-3),tank=(2,-2),left_shoulder=(-1,-1),right_shoulder=(1,-2),chest=(0,-2),hips=(0,0),left_leg=(-2,0),right_leg=(2,0),right_arm=(1,-2)),
    'strike':dict(head=(-3,3),tank=(-2,2),left_shoulder=(-3,3),right_shoulder=(-1,2),chest=(-2,2),hips=(1,1),left_leg=(-2,0),right_leg=(2,0),right_arm=(-1,2)),
    'stuck':dict(head=(-2,2),tank=(-1,2),left_shoulder=(-2,2),right_shoulder=(-1,2),chest=(-1,2),hips=(1,1),left_leg=(-2,0),right_leg=(2,0),right_arm=(-1,2)),
    'recover':dict(head=(2,-1),tank=(3,-1),left_shoulder=(1,0),right_shoulder=(2,-1),chest=(1,0),hips=(0,0),left_leg=(-1,0),right_leg=(1,0),right_arm=(2,0)),
}
MOTION_PIVOTS={'windup':(7,21),'held':(3,18),'strike':(4,23),'stuck':(5,23),'recover':(6,20)}
FREE_ARM_ANGLES={'windup':270,'held':90,'strike':270,'stuck':90,'recover':0}
ORIGIN=(16,16)

def rotate(x,y,angle):
    return (x,y) if angle==0 else (-y,x) if angle==90 else (-x,-y) if angle==180 else (y,-x)

def component(points,local_pivot,angle,world_pivot,palette):
    transformed=[]
    for x,y,v in points:
        rx,ry=rotate(x-local_pivot[0],y-local_pivot[1],angle)
        transformed.append((rx,ry,v))
    x0=min(x for x,y,v in transformed);y0=min(y for x,y,v in transformed)
    assert max(x for x,y,v in transformed)-x0<16 and max(y for x,y,v in transformed)-y0<16
    tile=[[0]*16 for _ in range(16)]
    for x,y,v in transformed:tile[y-y0][x-x0]=v
    return dict(x=world_pivot[0]+x0,y=world_pivot[1]+y0,palette=palette,tile=tile)

def render(entries,pages):
    result=Image.new('RGBA',(64,64))
    for entry in reversed(entries):
        char=entry['char'];sheet=pages[char>>6];tx,ty=(char&15)*8,((char&63)//16)*8
        for y in range(16):
            for x in range(16):
                v=sheet[ty+y][tx+x]
                px,py=entry['x']+x+ORIGIN[0],entry['y']+y+ORIGIN[1]
                if v:
                    assert 0<=px<64 and 0<=py<64, 'opaque pixel outside preview canvas'
                    result.putpixel((px,py),pack.rgb(pack.PALETTES[entry['palette']][v])+(255,))
    return result

def articulated_body(body):
    """Partition native pixels into nine joints, simplifying sparse accents."""
    groups={};accent_changes=[]
    for y,row in enumerate(body):
        for x,value in enumerate(row):
            if not value:continue
            if y<=17 and 10<=x<=21:name='head'
            elif y<=17 and x>=22:name='tank' if value in (1,8,9) else 'right_shoulder'
            elif y<=22 and x<=11:name='left_shoulder'
            elif y<=22 and x>=21:name='right_shoulder'
            elif y<=30 and 8<=x<=23:name='chest'
            elif 22<=y<=31 and x>=23:name='right_arm'
            elif 29<=y<=36 and 9<=x<=21:name='hips'
            elif x<16:name='left_leg'
            else:name='right_leg'
            v=value
            if name in ('head','hips','left_leg','right_leg') and value in (8,9):
                v=1 if value==8 else (2 if name=='hips' else 6)
                accent_changes.append(dict(x=x,y=y,before=value,after=v,part=name))
            groups.setdefault(name,[]).append((x,y,v))
    # Overlap existing waist and thigh-cuff pixels at the joint. The original
    # rigid suit had edge-to-edge cuts; spreading the feet otherwise exposes
    # a transparent gap between the belt and the left thigh. These are copied
    # native pixels, not a new outline or a painted background patch.
    normal={(x,y):v for points in groups.values() for x,y,v in points}
    joint_overlap=[]
    for y in range(29,36):
        for x in range(6,22):
            if not ((x<=9 and y>=31) or (x>=9 and y<=32)):continue
            if (x,y) in normal:
                v=normal[x,y];groups['hips'].append((x,y,v));joint_overlap.append([x,y,v])
    pieces=[]
    # Tank behind the torso, skull and shoulder plates in front of joints.
    for name in ('head','left_shoulder','right_shoulder','right_arm','chest','hips','left_leg','right_leg','tank'):
        points=groups[name];x0=min(x for x,y,v in points);y0=min(y for x,y,v in points)
        assert max(x for x,y,v in points)-x0<16 and max(y for x,y,v in points)-y0<16
        for palette in ('warden_armor','warden_iron'):
            tile=[[0]*16 for _ in range(16)]
            for x,y,v in points:
                if palette=='warden_armor' and v<=7:tile[y-y0][x-x0]=v
                elif palette=='warden_iron' and v in (8,9):tile[y-y0][x-x0]=v-6
            if any(v for row in tile for v in row):pieces.append(dict(name=name,x=x0,y=y0,palette=palette,tile=tile))
    reconstructed=[[0]*32 for _ in range(48)]
    for name,points in groups.items():
        for x,y,v in points:reconstructed[y][x]=v
    expected=[r.copy() for r in body]
    for change in accent_changes:expected[change['y']][change['x']]=change['after']
    assert reconstructed==expected
    return pieces,accent_changes,joint_overlap

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rigged-pack',type=Path,required=True)
    ap.add_argument('--accepted',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--body-motion',action='store_true',help='articulated suit variant, retiring the old near-static brace/vent cells')
    ap.add_argument('--compare-to',type=Path,help='earlier native pose folder for a synchronized before/after loop')
    args=ap.parse_args();out=args.output;assert not out.exists(),'fresh output required'
    report=json.loads((args.rigged_pack/'RECEIPT.json').read_text())
    assert report['charge_rig_reuses_side_tiles'] and report['unique_obj_cells']==45
    pages=[pack.sheet_codec.sheet_to_grid((args.rigged_pack/f'actor-page-{i}.3bpp').read_bytes()) for i in range(4)]
    retired=('warden_brace','warden_vent') if args.body_motion else ()
    kept={n:f for n,f in report['frames'].items() if n not in retired}
    baseline=29 if args.body_motion else 45
    used={e['char'] for frame in kept.values() for e in frame['oam']};allocated={}
    for char in sorted(used):
        sheet=pages[char>>6];tx,ty=(char&15)*8,((char&63)//16)*8
        allocated[bytes(v for y in range(16) for v in sheet[ty+y][tx:tx+16])]=char
    assert len(allocated)==baseline
    cells=[q+r+x for q in (0,0x40,0x80,0xC0) for r in (0,0x20) for x in range(0,16,2) if q+r+x not in pack.RESERVED and q+r+x not in used]
    assert len(cells)==58-baseline
    front=[[0 if c=='.' else int(c) for c in row] for row in (args.accepted/'warden_idle_front-roles.txt').read_text().splitlines()]
    body=[row.copy() for row in front];mask=[];arm=[]
    for y,row in enumerate(front):
        for x,v in enumerate(row):
            if (22<=y<=31 and x<=8) or (32<=y<=43 and x<=5):
                mask.append([x,y]);body[y][x]=0
                if 22<=y<=31 and 1<=v<=7:arm.append((x,y,v))
    # The selected split alone is lossless. Only the explicitly masked source
    # arm/weapon is replaced; every other accepted body pixel remains exact.
    reconstructed=[row.copy() for row in body]
    for x,y in mask:reconstructed[y][x]=front[y][x]
    assert reconstructed==front
    anchor=[]
    for y,row in enumerate(ANCHOR):
        assert len(row)==16
        for x,c in enumerate(row):
            if c!='.':anchor.append((x,y,int(c)))
    body_tiles=pack.tiles_for_warden(body);accent_changes=[];joint_overlap=[]
    if args.body_motion:body_tiles,accent_changes,joint_overlap=articulated_body(body)
    poses=[dict(p) for p in POSES]
    if args.body_motion:
        for pose in poses:pose['pivot']=MOTION_PIVOTS[pose['name']]
        poses[3]['anchor_grip']=(2,31)
    frames={};images={};newcells=[];components={}
    for pose in poses:
        angle=pose['angle'];pivot=pose['pivot']
        dx,dy=rotate(4-6,30-22,angle);grip=(pivot[0]+dx,pivot[1]+dy)
        anchor_grip=pose.get('anchor_grip',grip)
        arm_piece=component(arm,(6,22),angle,pivot,'warden_armor')
        anchor_piece=component(anchor,(7,3),angle,anchor_grip,'warden_iron')
        pieces=[anchor_piece,arm_piece]
        for original in body_tiles:
            piece=dict(original)
            if args.body_motion:
                dx,dy=BODY_OFFSETS[pose['name']][piece['name']]
                if piece['name']=='right_arm':
                    points=[(piece['x']+x,piece['y']+y,v) for y,row in enumerate(piece['tile']) for x,v in enumerate(row) if v]
                    piece=component(points,(24,23),FREE_ARM_ANGLES[pose['name']],(24+dx,23+dy),piece['palette'])
                else:piece['x']+=dx;piece['y']+=dy
            elif piece['y']<32:piece['y']+=pose['mass']
            pieces.append(piece)
        entries=[]
        for piece in pieces:
            tile=piece['tile'];key=bytes(v for row in tile for v in row)
            assert all(0<=v<=7 for v in key)
            if key not in allocated:
                assert len(newcells)<len(cells),'anchor slam exceeds available native cells'
                char=cells[len(newcells)];newcells.append(char);allocated[key]=char
                sheet=pages[char>>6];tx,ty=(char&15)*8,((char&63)//16)*8
                for y,row in enumerate(tile):sheet[ty+y][tx:tx+16]=row
            entries.append(dict(char=allocated[key],x=piece['x'],y=piece['y'],palette=piece['palette']))
        images[pose['name']]=render(entries,pages)
        frames[pose['name']]=dict(oam=entries,arm_angle=angle,shoulder=pivot,hand_grip=grip,anchor_grip=anchor_grip,
                                  mass_offset=pose['mass'],preview_duration_frames=pose['frames'],
                                  body_offsets=BODY_OFFSETS[pose['name']] if args.body_motion else {},
                                  free_arm_angle=FREE_ARM_ANGLES[pose['name']] if args.body_motion else 0,
                                  max_scanline_objects=max(sum(e['y']<=y<e['y']+16 for e in entries) for y in range(-16,48)))
        components[pose['name']]=[arm_piece,anchor_piece]
    # Adding attack pieces must never alter a previously allocated source cell.
    for char in used | {0xC0,0xC2,0xE0,0xE2}:
        before=pack.sheet_codec.sheet_to_grid((args.rigged_pack/f'actor-page-{char>>6}.3bpp').read_bytes())
        tx,ty=(char&15)*8,((char&63)//16)*8
        assert all(pages[char>>6][ty+y][tx:tx+16]==before[ty+y][tx:tx+16] for y in range(16))
    for char in (0x20,0x22):assert char not in newcells
    out.mkdir(parents=True)
    for i,page in enumerate(pages):
        raw=pack.sheet_codec.grid_to_sheet(page);assert pack.sheet_codec.sheet_to_grid(raw)==page
        stream=pack.lz2.compress(raw);assert pack.lz2.decompress(stream,max_output=1536)==(raw,len(stream))
        (out/f'actor-page-{i}.3bpp').write_bytes(raw);(out/f'actor-page-{i}.txt').write_text(pack.sheet_codec.grid_to_text(page))
        (out/f'actor-page-{i}.lz2').write_bytes(stream)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',23)
    small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
    board=Image.new('RGB',(1480,700),'#252a2d');d=ImageDraw.Draw(board)
    d.text((24,16),'Pirate warden — '+('articulated body' if args.body_motion else 'anchor slam')+' native rig preview',font=font,fill='white')
    d.text((24,53),'Head, shoulders, chest, tank and hips shift over a wider stance. Preview only; private ROM unchanged.' if args.body_motion else 'Accepted body + extracted weapon arm + new indexed iron anchor. Preview only; private ROM unchanged.',font=small,fill='#c7d1ca')
    animation=[];durations=[]
    for col,pose in enumerate(poses):
        name=pose['name'];im=images[name];im.save(out/(name+'-native.png'))
        x=24+col*290;d.text((x,96),name.title(),font=font,fill='white')
        d.line((x,120+60*4,x+256,120+60*4),fill='#63756b')
        big=im.resize((256,256),Image.Resampling.NEAREST);board.paste(big,(x,120),big)
        board.paste(im,(x+94,408),im)
        d.text((x,490),f'{len(frames[name]["oam"])} OBJ pieces / {pose["frames"]} preview frames',font=small,fill='#c7d1ca')
        d.text((x,520),f'Head offset {BODY_OFFSETS[name]["head"]}' if args.body_motion else f'Arm angle {pose["angle"]} degrees',font=small,fill='#c7d1ca')
        frame=Image.new('RGB',(512,384),'#252a2d');fd=ImageDraw.Draw(frame)
        fd.text((20,14),'ANCHOR SLAM — preview, not gameplay',font=small,fill='white')
        fd.line((20,320,492,320),fill='#63756b')
        enlarged=im.resize((256,256),Image.Resampling.NEAREST);frame.paste(enlarged,(128,80),enlarged)
        fd.text((20,355),name.title(),font=small,fill='white');animation.append(frame);durations.append(round(pose['frames']*1000/60))
    total=baseline+len(newcells)
    d.text((24,586),f'Active base: {baseline} cells. Body/weapon rig adds {len(newcells)} cells. Combined pack: {total}/58; {58-total} free.',font=font,fill='white')
    d.text((24,625),'Idle/charge/protector and Princess preserved; old brace/vent cells reclaimed. No new colours.' if args.body_motion else 'Original actor cells and Princess preserved; Baby slots reserved. No new palette colours.',font=small,fill='#c7d1ca')
    d.text((24,655),'Timing is an art study. No hitboxes, damage, effects, screen shake or attack behavior added.',font=small,fill='#c7d1ca')
    board.save(out/'anchor-slam-frames.png')
    animation[0].save(out/'anchor-slam-motion.gif',save_all=True,append_images=animation[1:],duration=durations,loop=0,optimize=False)
    if args.compare_to:
        comparison=[]
        for pose in poses:
            name=pose['name'];frame=Image.new('RGB',(960,400),'#252a2d');fd=ImageDraw.Draw(frame)
            for x,label,path in ((0,'Previous: arm only',args.compare_to/(name+'-native.png')),(480,'Revised: body and counterbalance',out/(name+'-native.png'))):
                fd.text((x+20,15),label,font=small,fill='white')
                im=Image.open(path).convert('RGBA');assert im.size==(64,64)
                im=im.resize((256,256),Image.Resampling.NEAREST);frame.paste(im,(x+100,70),im)
                fd.line((x+20,310,x+460,310),fill='#63756b')
            fd.text((20,360),name.title()+' — native art timing study; ROM unchanged',font=small,fill='#c7d1ca');comparison.append(frame)
        comparison[0].save(out/'body-motion-comparison.gif',save_all=True,append_images=comparison[1:],duration=durations,loop=0,optimize=False)
    result=dict(status='NATIVE_RIG_ATTACK_PREVIEW_ONLY',rigged_pack_receipt_sha256=hashlib.sha256((args.rigged_pack/'RECEIPT.json').read_bytes()).hexdigest(),
                body_source_sha256=hashlib.sha256((args.accepted/'warden_idle_front-roles.txt').read_bytes()).hexdigest(),
                source_mask=mask,original_body_split_exact=True,original_allocated_cells_unchanged=True,
                baseline_obj_cells=baseline,new_obj_cells=[f'{c:02X}' for c in newcells],total_obj_cells=total,capacity=58,
                articulated_body=args.body_motion,accent_changes=accent_changes,retired_legacy_frame_cells=list(retired),
                protected_legacy_frames=list(kept),retired_legacy_art_removed_from_candidate=bool(retired),
                joint_overlap_source_pixels=joint_overlap,
                free_obj_cells=58-total,frames=frames,palette_words=report['palettes'],rom_written=False,
                source_binding_installed=False,native_runtime_qualified=False)
    # Standing-side is an unused runtime frame in the existing D4 AI. Its art
    # remains resident for rigged charge; omit only that standalone table entry
    # when preparing a future combined binding, retaining the current 8-bit ABI.
    omitted=['warden_idle_side']
    if args.body_motion:omitted+=['protector_idle_front','protector_idle_side']
    runtime_frames={name:f for name,f in kept.items() if name not in omitted}
    runtime_frames.update({'warden_slam_'+name:f for name,f in frames.items()})
    entries=sum(len(f['oam']) for f in runtime_frames.values())
    assert entries<128,'combined runtime coordinate tables exceed 8-bit doubled index'
    assert max(len(f['oam']) for f in runtime_frames.values())<=32
    result['runtime_table_plan']=dict(omitted_preview_frames=omitted,art_cells_removed=False,
                                      frame_names=list(runtime_frames),entries=entries,coordinate_bytes_per_axis=entries*2,
                                      sprite_oam_count_minus_one=max(len(f['oam']) for f in runtime_frames.values())-1,
                                      legacy_frame_aliases={'warden_brace':'warden_slam_held','warden_vent':'warden_slam_recover'} if args.body_motion else {},installed=False)
    (out/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','baseline_obj_cells','new_obj_cells','total_obj_cells','free_obj_cells','rom_written')},indent=2))

if __name__=='__main__':main()
