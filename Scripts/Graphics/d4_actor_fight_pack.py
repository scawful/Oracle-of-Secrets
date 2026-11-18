#!/usr/bin/env python3
"""Compile the approved D4 art into a bounded complete fight source bundle.

Emit files for review/copy into an owned source checkout; never write a ROM.
Records use signed byte offsets and per-frame pointers in bank $47:C000.
"""
from pathlib import Path
import argparse,copy,hashlib,json
from PIL import Image,ImageDraw,ImageFont
import warden_walk_preview as w
pack=w.pack
ROWS=pack.PALETTE_ROWS
DIRECTIONS=('right','left','front','rear')
CHARGE=('brace','stride_a','stride_b','brake')
SLAM=('windup','held','strike','stuck','recover')
VENT_STEAM_A=(
    '....111111......',
    '...15666651.....',
    '..1566666651....',
    '..1666666661....',
    '..1566666651....',
    '...1156651111...',
    '.....15656651...',
    '....156666661...',
    '....15666651....',
    '.....115511.....',
    '......1561......',
    '......1651......',
    '.......11.......',
    '.......11.......',
    '................',
    '................',
)
VENT_STEAM_B=(
    '...1111111......',
    '..156666651.....',
    '.15666666651....',
    '.16666666661....',
    '..1566666511....',
    '...1115515651...',
    '....1566666651..',
    '...15666666651..',
    '...1566666511...',
    '....1115511.....',
    '.....15651......',
    '.....1561.......',
    '......11........',
    '................',
    '................',
    '................',
)
SLAM_FLOOR_CRACK=(
    '................',
    '................',
    '................',
    '................',
    '................',
    '................',
    '................',
    '................',
    '..161......161..',
    '.14641....14641.',
    '..111111111111..',
    '.12211244211221.',
    '121..111111..121',
    '......1..1......',
    '................',
    '................',
)

def write_cell(pages,char,pattern):
    assert len(pattern)==16 and all(len(r)==16 for r in pattern)
    tx,ty=(char&15)*8,((char&63)//16)*8
    for y,row in enumerate(pattern):
        pages[char>>6][ty+y][tx:tx+16]=[0 if ch=='.' else int(ch) for ch in row]

def render_frame(entries,pages,canvas=(64,64)):
    im=Image.new('RGBA',tuple(canvas))
    for e in reversed(entries):
        tile=w.tile_at(pages,e['char']);pal=pack.PALETTES[e['palette']]
        for y in range(16):
            for x in range(16):
                v=tile[y][15-x if e.get('flip_x') else x]
                if v:
                    px,py=e['x']+x+16,e['y']+y+16
                    assert 0<=px<canvas[0] and 0<=py<canvas[1],(px,py,canvas)
                    im.putpixel((px,py),pack.rgb(pal[v])+(255,))
    return im

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('attacks','walk','body','base','output'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();out=a.output;assert not out.exists()
    at=json.loads((a.attacks/'RECEIPT.json').read_text());wa=json.loads((a.walk/'RECEIPT.json').read_text());bo=json.loads((a.body/'RECEIPT.json').read_text());ba=json.loads((a.base/'RECEIPT.json').read_text())
    assert at['total_cells']==51
    pages=[pack.sheet_codec.sheet_to_grid((a.attacks/f'actor-page-{i}.3bpp').read_bytes()) for i in range(4)]
    frames={}
    for direction in DIRECTIONS:
        for i in range(4):frames[f'{direction}_walk_{i}']=dict(oam=copy.deepcopy(wa['frames'][f'{direction}_{i}']['oam']),kind='warden',canvas=[64,64])
    # Front charge has a low anchor and compressed head/shoulders, distinct
    # from the approved overhead slam. Only existing native pieces move.
    for i,key in enumerate(CHARGE):
        entries=copy.deepcopy(wa['frames'][f'front_{i}']['oam'])
        for e in entries:
            part=e.get('part')
            if part=='head':e['y']+=2 if key=='brace' else 2 if key.startswith('stride') else 1
            elif part in ('chest','left_shoulder','right_shoulder'):e['y']+=2 if key=='brace' else 1
            elif key=='brace' and part in ('right_arm','tank'):e['y']+=2
            elif part in ('anchor','weapon_arm') and key.startswith('stride'):e['x']-=1
        frames[f'front_charge_{key}']=dict(oam=entries,kind='warden',canvas=[64,64])
    for name,f in at['frames'].items():frames[name]=dict(oam=copy.deepcopy(f['oam']),kind='warden',canvas=[64,64])
    for key,f in bo['frames'].items():frames[f'front_slam_{key}']=dict(oam=copy.deepcopy(f['oam']),kind='warden',canvas=[64,64])
    for name,f in ba['frames'].items():
        if name.startswith('protector'):frames[name]=dict(oam=copy.deepcopy(f['oam']),kind='protector',canvas=[16,24])
    # Fix 1: reuse 90-degree horizontal weapon_arm + anchor from *_slam_windup in all 4 *_charge_brace poses.
    for direction in ('front','left','rear'):
        windup={e.get('part'):e for e in frames[f'{direction}_slam_windup']['oam'] if e.get('part')}
        if direction=='front':
            arm_src=next(e for e in frames['front_slam_windup']['oam'] if e['char']==0x64)
            anch_src=next(e for e in frames['front_slam_windup']['oam'] if e['char']==0x62)
            for e in frames['front_charge_brace']['oam']:
                if e.get('part')=='weapon_arm':e.update(char=arm_src['char'],x=-2,y=18,palette=arm_src['palette'],flip_x=False)
                elif e.get('part')=='anchor':e.update(char=anch_src['char'],x=-13,y=15,palette=anch_src['palette'],flip_x=False)
        elif direction=='left':
            arm_src=windup['weapon_arm'];anch_src=windup['anchor']
            for e in frames['left_charge_brace']['oam']:
                p=e.get('part')
                if p=='head':e['y']+=1
                elif p in ('chest','tank','hose'):e['y']+=1
                elif p=='weapon_arm':e.update(char=arm_src['char'],x=8,y=15,palette=arm_src['palette'],flip_x=False)
                elif p=='anchor':e.update(char=anch_src['char'],x=-3,y=13,palette=anch_src['palette'],flip_x=False)
            frames['right_charge_brace']=dict(oam=w.mirror(frames['left_charge_brace']['oam']),kind='warden',canvas=[64,64])
        elif direction=='rear':
            arm_src=next(e for e in frames['rear_slam_windup']['oam'] if e['char']==0x64)
            anch_src=next(e for e in frames['rear_slam_windup']['oam'] if e['char']==0x62)
            for e in frames['rear_charge_brace']['oam']:
                p=e.get('part')
                if p in ('head','back_tank','left_shoulder','right_shoulder','right_arm','tank'):e['y']+=1
                elif p=='weapon_arm':e.update(char=arm_src['char'],x=18,y=17,palette=arm_src['palette'],flip_x=True)
                elif p=='anchor':e.update(char=anch_src['char'],x=29,y=14,palette=anch_src['palette'],flip_x=True)
    # Fix 2: outlined 2-frame steam plume ($26, $28) + floor-crack tile ($2A) in free atlas cells.
    c=int(at['free_cell_indices'][0],16)
    c_steam_b=int(at['free_cell_indices'][1],16)
    c_crack=int(at['free_cell_indices'][2],16)
    assert (c,c_steam_b,c_crack)==(0x26,0x28,0x2A),(c,c_steam_b,c_crack)
    write_cell(pages,c,VENT_STEAM_A)
    write_cell(pages,c_steam_b,VENT_STEAM_B)
    write_cell(pages,c_crack,SLAM_FLOOR_CRACK)
    # Fix 2: lower *_slam_stuck anchor +6px Y, slump upper body, and prepend floor-crack tile $2A.
    for direction in DIRECTIONS:
        f=frames[f'{direction}_slam_stuck'];f['canvas']=[64,72];entries=f['oam']
        anchor=None
        for e in entries:
            part=e.get('part');ch=e['char']
            if part=='anchor' or ch==0xC4:
                e['y']+=6;anchor=e
            elif part=='head' or ch in (0x02,0x66,0xCC):
                e['y']+=2
            elif part in ('chest','left_shoulder','right_shoulder','tank','hose','back_tank','weapon_arm','right_arm') or ch in (0x68,0x6A,0x80,0x82,0x8A,0x8C,0xC6,0xAE,0x6E,0xCE):
                e['y']+=1
        assert anchor is not None,direction
        entries.insert(0,dict(char=c_crack,x=anchor['x'],y=anchor['y']+3,palette='warden_armor',flip_x=bool(anchor.get('flip_x',False)),part='floor_crack'))
    # Fix 2: slumped *_vent OAM (head +4, chest/shoulders/anchor/tank +3), back_tank -> warden_armor, 2-frame plume ($26/$28).
    for direction in DIRECTIONS:
        base_entries=copy.deepcopy(frames[f'{direction}_charge_brake']['oam'])
        for e in base_entries:
            part=e.get('part')
            if part=='head':e['y']+=4
            elif part in ('chest','left_shoulder','right_shoulder','anchor','weapon_arm','right_arm','tank','hose'):e['y']+=3
            elif part=='back_tank':
                e['y']+=3;e['palette']='warden_armor'
        sx,sy={'front':(22,-2),'left':(22,2),'right':(-6,2),'rear':(8,-3)}[direction]
        sfx=(direction=='right')
        for suffix,char_id in (('vent',c),('vent_b',c_steam_b)):
            vent_entries=copy.deepcopy(base_entries)
            vent_entries.insert(0,dict(char=char_id,x=sx,y=sy,palette='warden_armor',flip_x=sfx,part='vent_steam'))
            frames[f'{direction}_{suffix}']=dict(oam=vent_entries,kind='warden',canvas=[64,64])
    assert len(frames)<128
    out.mkdir(parents=True);binding=out/'binding';binding.mkdir()
    ids={n:i for i,n in enumerate(frames)}
    lines=['; GENERATED by Scripts/Graphics/d4_actor_fight_pack.py.',
           '; Private D4 frame records in the source graphics bank. M/X=8 draw ABI.',
           '!D4Zora_FrameBank = $47']
    for name,i in ids.items():lines.append(f'!D4Zora_Frame_{name} = {i}')
    lines+=['pushpc','org $47C000','D4Zora_FrameDataStart:','D4Zora_FramePointers:']
    lines+=['  dw '+', '.join(f'D4Zora_Frame_{i}_Data&$FFFF' for i in ids.values()),'D4Zora_FrameCounts:',
            '  db '+', '.join(str(len(f['oam'])) for f in frames.values())]
    lookup={}
    for label,keys in [('Walk',[f'{d}_walk_{i}' for d in DIRECTIONS for i in range(4)]),
                       ('Charge',[f'{d}_charge_{k}' for d in DIRECTIONS for k in CHARGE]),
                       ('Slam',[f'{d}_slam_{k}' for d in DIRECTIONS for k in SLAM]),
                       ('Vent',[f'{d}_{p}' for d in DIRECTIONS for p in ('vent','vent_b')])]:
        values=[ids[n] for n in keys];lookup[label]=values;lines += [f'D4Warden_{label}Frames:','  db '+', '.join(str(v) for v in values)]
    for name,palette in pack.PALETTES.items():lines += [f'D4Zora_Palette_{name}:','  dw '+', '.join(f'${v:04X}' for v in palette[1:])]
    for i,(name,f) in enumerate(frames.items()):
        origin=(-8,-24) if f['kind']=='warden' else (-8,-16);f['runtime_origin']=list(origin);lines.append(f'D4Zora_Frame_{i}_Data: ; {name}')
        for e in f['oam']:
            x,y=e['x']+origin[0],e['y']+origin[1];assert -128<=x<128 and -128<=y<128
            props=0x31|(ROWS[e['palette']]<<1)|(0x40 if e.get('flip_x') else 0)
            lines.append(f'  db ${x&255:02X}, ${y&255:02X}, ${e["char"]:02X}, ${props:02X}')
        if f['kind']=='warden':im=render_frame(f['oam'],pages,f['canvas'])
        else:im=render_frame(f['oam'],pages,(64,64)).crop((16,16,32,40))
        im.save(out/(name+'-native.png'))
    lines+=['D4Zora_FrameDataEnd:','assert D4Zora_FrameDataEnd <= $47D000, "D4 frame records exceed audited 4KiB tail"','pullpc','']
    (binding/'frames.asm').write_text('\n'.join(lines))
    spec=json.loads((pack.ROOT/'Data/graphics/source_sprite_sheets.json').read_text());spec['schema_version']=2
    existing_d4=pack.ROOT/'Data/graphics/d4_zora_sprite_sheets.json'
    extra_entries=[]
    if existing_d4.is_file():
        cur_d4=json.loads(existing_d4.read_text())
        extra_entries=[e for e in cur_d4['sheets'][len(spec['sheets']):] if e.get('global_sheet') not in ('0xDF','0xE0','0xE1','0xE2')]
    sheets=[]
    for i,page in enumerate(pages):
        raw=pack.sheet_codec.grid_to_sheet(page);assert pack.sheet_codec.sheet_to_grid(raw)==page
        (out/f'actor-page-{i}.3bpp').write_bytes(raw);text=pack.sheet_codec.grid_to_text(page);(binding/f'atlas-{0xDF+i:02X}.txt').write_text(text)
        sha=hashlib.sha256(raw).hexdigest();sheets.append(dict(page=i,sha256=sha))
        spec['sheets'].append(dict(global_sheet=f'0x{0xDF+i:02X}',source=f'd4_zora/atlas-{0xDF+i:02X}.txt',decoded_sha256=sha,why='D4 complete private warden/protector fight; preserves Princess and Baby upload slots.'))
    spec['sheets'].extend(extra_entries)
    (binding/'d4_zora_sprite_sheets.json').write_text(json.dumps(spec,indent=2)+'\n')
    board=Image.new('RGB',(1080,400),'#252a2d');d=ImageDraw.Draw(board);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',21)
    d.text((20,12),'Completed front charge — private fight binding input',font=font,fill='white')
    for i,key in enumerate(CHARGE):
        x=20+i*265;d.text((x,50),key.replace('_',' '),font=font,fill='white');im=Image.open(out/f'front_charge_{key}-native.png');big=im.resize((256,256),Image.Resampling.NEAREST);board.paste(big,(x,85),big)
    board.save(out/'front-charge-complete.png')
    record_bytes=sum(len(f['oam'])*4 for f in frames.values());header_bytes=len(frames)*3+sum(map(len,lookup.values()))+56
    assert record_bytes+header_bytes<=4096
    result=dict(schema_version=2,status='FULL_FIGHT_BINDING_INPUT',frames=frames,frame_ids=ids,lookups=lookup,sheets=sheets,
                palettes={n:[f'{v:04X}' for v in p] for n,p in pack.PALETTES.items()},directions=list(DIRECTIONS),
                total_cells=54,capacity=58,free_cells=4,steam_char=f'{c:02X}',steam_chars=[f'{c:02X}',f'{c_steam_b:02X}'],floor_crack_char=f'{c_crack:02X}',frame_region=['47C000','47D000'],
                frame_bytes=record_bytes+header_bytes,max_oam=max(len(f['oam']) for f in frames.values()),
                room_spriteset='4F',native_runtime_qualified=False,rom_written=False)
    (out/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n');(binding/'frames.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','total_cells','free_cells','frame_bytes','max_oam')},indent=2));print('Frames:',len(frames))

if __name__=='__main__':main()
