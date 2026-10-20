#!/usr/bin/env python3
"""Pack approved indexed Ganondorf art into one resident SNES 4bpp sheet.

Source: Data/graphics/ganondorf/{canonical.png,project.json}.
Generated: Sprites/Bosses/{ganondorf.bin,ganondorf.pal,ganondorf_frames.asm}.
The source is never resampled or quantized. Both fixed and first-opaque-row
16x16 layouts undergo full planar decode and reconstruction before selection.
No ROM is read, written or built. Requires Pillow.
"""
from __future__ import annotations
import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import tempfile
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT = ROOT / 'Data/graphics/ganondorf/project.json'
BODY_IDS = ('idle', 'cast', 'hurt', 'release', 'side', 'back_a', 'back_b',
            'cast_ready', 'cast_half', 'cast_a', 'cast_second', 'cast_b',
            'throw_windup', 'throw', 'throw_follow', 'recover_half')
SOURCE_IDS = BODY_IDS + ('ball_a', 'ball_b', 'bat_up', 'bat_mid', 'bat_down')
# Keep superseded art in the editable source without spending resident VRAM on it.
PACKED_IDS = tuple(name for name in SOURCE_IDS if name not in ('cast', 'release', 'side'))
RUNTIME_IDS = ('idle', 'cast', 'hurt', 'ball_a', 'ball_b', 'release',
               'right', 'left', 'back_a', 'back_b', 'charge_a', 'charge_b',
               'cast_ready', 'cast_half', 'cast_a', 'cast_second',
               'throw_windup', 'throw_follow', 'recover_half',
               'bat_up', 'bat_mid', 'bat_down')
BODY_ALIASES = {'cast': 'cast_b', 'release': 'throw', 'right': 'idle', 'left': 'idle'}
HELD_BALL_FRAMES = ('charge_a', 'charge_b', 'cast_a', 'cast_second')
TABLE_NAMES = ('start_index', 'nbr_of_tiles', 'x_offsets', 'y_offsets',
               'chr', 'properties', 'sizes')
SHEET_SIZE = (128, 96)
SHEET_BYTES = 0x1800
MAX_CELLS = 48
BASE_PROPERTIES = 0x3D  # OBJ palette6; palette4 is reserved for vanilla shadows.
VIEW_ORIGIN = (16, 40)
VIEW_SIZE = (64, 80)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def indexed(size, palette):
    image = Image.new('P', size, 0)
    image.putpalette([channel for color in palette for channel in color] + [0] * 720)
    image.info['transparency'] = 0
    return image


def load_source(path):
    raw = path.read_bytes()
    project = json.loads(raw)
    if project.get('schema') != 1 or project.get('frame_grid') != [32, 48] or project.get('columns') != 8:
        raise ValueError('source schema/grid must be1 /32x48 /8columns')
    palette = [tuple(bytes.fromhex(color.removeprefix('#'))) for color in project['palette']]
    if len(palette) != 16 or any(len(color) != 3 for color in palette):
        raise ValueError('exactly16 RGB palette colors required')
    image_path = (path.parent / project['image']).resolve()
    if image_path.parent != path.parent.resolve():
        raise ValueError('source image must reside beside project.json')
    image_raw = image_path.read_bytes()
    image = Image.open(BytesIO(image_raw)); image.load()
    if image.mode != 'P' or image.width != 256 or image.height % 48:
        raise ValueError('canonical source must be indexed256-wide with48px rows')
    if image.getpalette()[:48] != [c for rgb in palette for c in rgb] or image.info.get('transparency') != 0:
        raise ValueError('source palette/transparency mismatch')
    if max(image.tobytes()) > 15:
        raise ValueError('source palette index exceeds15')
    images = {}; occupied = set(); used = indexed(image.size, palette)
    for frame in project['frames']:
        name = frame['id']; col, row = frame['cell']; width, height = frame['size']
        if name not in SOURCE_IDS or name in images:
            raise ValueError(f'unknown/duplicate frame:{name}')
        expected_size = (16, 16) if name.startswith(('ball_', 'bat_')) else (32, 40)
        if (width, height) != expected_size:
            raise ValueError(f'{name}: expected{expected_size}')
        if (col, row) in occupied or not 0 <= col < 8 or not 0 <= row < image.height // 48:
            raise ValueError(f'{name}: duplicate/out-of-bounds cell')
        occupied.add((col, row))
        cell = image.crop((col*32, row*48, col*32+32, row*48+48))
        part = cell.crop((0, 0, width, height))
        check = indexed((32, 48), palette); check.paste(part, (0, 0))
        if check.tobytes() != cell.tobytes():
            raise ValueError(f'{name}: pixels outside declared frame')
        images[name] = part
        used.paste(cell, (col*32, row*48))
    if set(images) != set(SOURCE_IDS) or used.tobytes() != image.tobytes():
        raise ValueError('missing source frame or pixels in unused cells')
    hashes = {'canonical_sha256': digest(image_raw), 'project_sha256': digest(raw)}
    return project, palette, images, hashes, image_path


def encode_4bpp(image):
    """SNES row-major8x8 tiles, planes0/1 followed by planes2/3."""
    if image.mode != 'P' or image.width % 8 or image.height % 8 or min(image.size) < 8:
        raise ValueError('4bpp input must be indexed with positive8px dimensions')
    pixels = image.tobytes()
    if max(pixels) > 15:
        raise ValueError('4bpp index exceeds15')
    result = bytearray()
    for top in range(0, image.height, 8):
        for left in range(0, image.width, 8):
            tile = bytearray(32)
            for y in range(8):
                for x in range(8):
                    value = pixels[(top+y)*image.width+left+x]
                    for plane in range(4):
                        tile[(plane//2)*16+y*2+plane%2] |= ((value >> plane) & 1) << (7-x)
            result.extend(tile)
    return bytes(result)


def decode_4bpp(data, width, palette):
    if width <= 0 or width % 8 or not data or len(data) % 32 or (len(data)//32) % (width//8):
        raise ValueError('4bpp data must fill complete8px tile rows')
    height = len(data)//32//(width//8)*8
    pixels = bytearray(width*height)
    for tile_index in range(len(data)//32):
        left = tile_index % (width//8)*8; top = tile_index // (width//8)*8
        tile = data[tile_index*32:tile_index*32+32]
        for y in range(8):
            for x in range(8):
                pixels[(top+y)*width+left+x] = sum(
                    ((tile[(plane//2)*16+y*2+plane%2] >> (7-x)) & 1) << plane
                    for plane in range(4))
    image = Image.frombytes('P', (width, height), bytes(pixels))
    image.putpalette([c for rgb in palette for c in rgb] + [0]*720)
    image.info['transparency'] = 0
    return image


def flipped(image, h=False, v=False):
    if h: image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if v: image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return image


def canonical_cell(image):
    variants = [(flipped(image, h, v), h, v) for h, v in
                ((False, False), (True, False), (False, True), (True, True))]
    image, h, v = min(variants, key=lambda item: item[0].tobytes())
    return image.tobytes(), image, h, v


def tile_piece(sheet, piece):
    tile = piece['tile']
    # A16x16 sprite addresses N,N+1,N+$10,N+$11 in the128px sheet.
    if tile & 1 or (tile//16) & 1 or tile+0x11 >= SHEET_BYTES//32:
        raise ValueError(f'invalid16x16 tile address:${tile:02X}')
    x = tile % 16*8; y = tile//16*8
    return flipped(sheet.crop((x, y, x+16, y+16)), piece['hflip'], piece['vflip'])


def paste_visible(canvas, part, position):
    canvas.paste(part, position, part.point(lambda index: 255 if index else 0, mode='L'))


def pack_layout(images, palette, align_body_top):
    cells = []; lookup = {}; maps = {}
    for name in PACKED_IDS:
        image = images[name]
        effect = name.startswith(('ball_', 'bat_'))
        ink = image.getbbox()
        top = ink[1] if ink and align_body_top and not effect else 0
        bottom = 16 if effect else 40
        right = 16 if effect else 32
        padded = indexed((64, 64), palette); padded.paste(image, (0, 0))
        pieces = []
        for y in range(top, bottom, 16):
            for x in range(0, right, 16):
                part = padded.crop((x, y, x+16, y+16))
                if not any(part.tobytes()): continue
                key, stored, h, v = canonical_cell(part)
                if key not in lookup:
                    lookup[key] = len(cells); cells.append(stored)
                slot = lookup[key]
                pieces.append(dict(tile=(slot//8)*32+(slot%8)*2,
                                   x=x, y=y, hflip=h, vflip=v, size=16))
        maps[name] = pieces
    # Evaluate larger losing candidates too; only the selected layout must fit.
    height = max(SHEET_SIZE[1], ((len(cells)+7)//8)*16)
    sheet = indexed((128, height), palette)
    for slot, part in enumerate(cells):sheet.paste(part, (slot%8*16, slot//8*16))
    data = encode_4bpp(sheet)
    decoded = decode_4bpp(data, 128, palette)
    if decoded.tobytes() != sheet.tobytes():raise ValueError('sheet4bpp roundtrip failed')
    # Reconstruction validates every visible pixel and transparent margin.
    for name, pieces in maps.items():
        reconstructed = indexed((64, 64), palette)
        for piece in pieces:
            tile = piece['tile']; x=tile%16*8; y=tile//16*8
            part = flipped(decoded.crop((x,y,x+16,y+16)),piece['hflip'],piece['vflip'])
            paste_visible(reconstructed,part,(piece['x'],piece['y']))
        expected = indexed((64,64),palette); expected.paste(images[name],(0,0))
        if reconstructed.tobytes()!=expected.tobytes():raise ValueError(f'{name}: packed pixels differ')
    return dict(name='first_opaque_row' if align_body_top else 'fixed',
                cells=len(cells), sheet=sheet, binary=data, maps=maps)


def runtime_maps(maps):
    frames = {}
    def body(name, mirror=False):
        return [dict(p, x=8-p['x'] if mirror else p['x']-8,
                     y=p['y']-16, hflip=p['hflip'] ^ mirror) for p in maps[name]]
    for name in RUNTIME_IDS:
        if name.startswith(('ball_', 'charge_', 'bat_')):continue
        frames[name]=body(BODY_ALIASES.get(name,name))
    for name in ('ball_a','ball_b'):
        if len(maps[name])!=1 or (maps[name][0]['x'],maps[name][0]['y'])!=(0,0):
            raise ValueError('ball must use one full16x16 piece at0,0')
        frames[name]=[dict(maps[name][0])]
    for letter in ('a','b'):
        frames['charge_'+letter]=body('cast_b')+[dict(maps['ball_'+letter][0],x=0,y=-32)]
    for name in ('cast_a', 'cast_second'):
        frames[name].append(dict(maps['ball_a'][0],x=0,y=-32))
    for name in ('bat_up', 'bat_mid', 'bat_down'):
        frames[name]=[dict(maps[name][0],x=0,y=-8)]
    if any(len(frames[name])>6 for name in RUNTIME_IDS if name not in HELD_BALL_FRAMES):
        raise ValueError('ordinary frame exceeds6 pieces')
    if any(len(frames[name])>7 for name in HELD_BALL_FRAMES):
        raise ValueError('charge exceeds7 pieces; shadow owns OAM index7')
    return frames


def make_asm(frames, hashes, selected):
    tables={name:[] for name in TABLE_NAMES}; cursor=0
    lines=['; Generated by Scripts/Generate/build_ganondorf_art.py; do not edit.',
           '; Approved original32x40 pixels; local labels included inside Ganon_DrawFrame.',
           f'; Canonical SHA256: {hashes["canonical_sha256"]}',
           f'; Layout: {selected["name"]}; {selected["cells"]}/{MAX_CELLS} unique16x16 cells.',
           '; Frames: '+', '.join(f'{i}={name}' for i,name in enumerate(RUNTIME_IDS)),
           '; Body x=source_x-8,y=source_y-16; balls0,0; charge ball0,-32.',
           '; X/Y offsets are signed16bit dw; draw loop indexes these tables with ASL.',
           '; Other tables are8bit db; max7 pieces; shadow owns OAM index7.','']
    for name in RUNTIME_IDS:
        pieces=frames[name]
        if not pieces:raise ValueError(f'{name}: zero-piece runtime frame')
        tables['start_index'].append(cursor);tables['nbr_of_tiles'].append(len(pieces)-1)
        for p in pieces:
            if not -32768<=p['x']<=32767 or not -32768<=p['y']<=32767:raise ValueError('signed16 offset overflow')
            tables['x_offsets'].append(p['x']&0xFFFF);tables['y_offsets'].append(p['y']&0xFFFF)
            tables['chr'].append(p['tile'])
            tables['properties'].append(BASE_PROPERTIES | (0x40 if p['hflip'] else 0) | (0x80 if p['vflip'] else 0))
            tables['sizes'].append(2)
        cursor+=len(pieces)
    if cursor>=128:raise ValueError('OAM table exceeds signed8bit indexing bound')
    for name in TABLE_NAMES:
        lines.append('.'+name)
        values=tables[name]
        word_offsets = name in ('x_offsets', 'y_offsets')
        directive, digits = ('dw', 4) if word_offsets else ('db', 2)
        for start in range(0,len(values),16):
            lines.append('  '+directive+' '+', '.join(f'${v:0{digits}X}' for v in values[start:start+16]))
    lines += ['', f'GanonBall_TileA = ${frames["ball_a"][0]["tile"]:02X}',
              f'GanonBall_TileB = ${frames["ball_b"][0]["tile"]:02X}']
    return '\n'.join(lines)+'\n',tables


def parse_asm_tables(text):
    tables={};current=None
    for line in text.splitlines():
        if line.startswith('.'):
            current=line[1:];tables[current]=[]
        elif line.strip().startswith(('db ', 'dw ')):
            directive = line.strip().split()[0]
            expected = 'dw' if current in ('x_offsets', 'y_offsets') else 'db'
            if directive != expected:raise ValueError(f'{current}: expected {expected} table')
            digits = 4 if directive == 'dw' else 2
            tokens = re.findall(r'\$([0-9A-F]+)',line)
            if any(len(token) != digits for token in tokens):raise ValueError(f'{current}: wrong operand width')
            tables[current].extend(int(token,16) for token in tokens)
    if set(tables)!=set(TABLE_NAMES):raise ValueError('generated table labels missing')
    return tables


def decode_runtime_tables(tables):
    frames={}
    signed=lambda n:n-0x10000 if n>=0x8000 else n
    for index,name in enumerate(RUNTIME_IDS):
        start=tables['start_index'][index];count=tables['nbr_of_tiles'][index]+1
        pieces=[]
        for n in range(start,start+count):
            if tables['sizes'][n]!=2:raise ValueError('runtime size must be16x16')
            prop=tables['properties'][n]
            if prop&0x3F != BASE_PROPERTIES:raise ValueError('base palette/page/priority properties changed')
            pieces.append(dict(tile=tables['chr'][n],x=signed(tables['x_offsets'][n]),
                               y=signed(tables['y_offsets'][n]),hflip=bool(prop&0x40),
                               vflip=bool(prop&0x80),size=16))
        frames[name]=pieces
    return frames


def render_runtime(sheet, pieces, palette):
    canvas=indexed(VIEW_SIZE,palette)
    for p in pieces:paste_visible(canvas,tile_piece(sheet,p),(p['x']+VIEW_ORIGIN[0],p['y']+VIEW_ORIGIN[1]))
    return canvas


def expected_runtime(name,images,palette):
    canvas=indexed(VIEW_SIZE,palette)
    if name in ('ball_a','ball_b'):
        paste_visible(canvas,images[name],VIEW_ORIGIN)
    else:
        source='cast_b' if name.startswith('charge_') else BODY_ALIASES.get(name,name)
        offset=(0,-8) if name.startswith('bat_') else (-8,-16)
        paste_visible(canvas,images[source],(VIEW_ORIGIN[0]+offset[0],VIEW_ORIGIN[1]+offset[1]))
        if name in HELD_BALL_FRAMES:
            ball='ball_'+name[-1] if name.startswith('charge_') else 'ball_a'
            paste_visible(canvas,images[ball],(VIEW_ORIGIN[0],VIEW_ORIGIN[1]-32))
    return canvas


def palette_binary(palette):
    words=[(r>>3)|((g>>3)<<5)|((b>>3)<<10) for r,g,b in palette]
    return b''.join(word.to_bytes(2,'little') for word in words)


def self_test():
    palette=[(index*17,)*3 for index in range(16)]
    vectors={1:bytes.fromhex('ff00'*8+'0000'*8),2:bytes.fromhex('00ff'*8+'0000'*8),
             4:bytes.fromhex('0000'*8+'ff00'*8),8:bytes.fromhex('0000'*8+'00ff'*8)}
    for value,expected in vectors.items():
        image=indexed((8,8),palette);image.paste(value,(0,0,8,8))
        if encode_4bpp(image)!=expected or decode_4bpp(expected,8,palette).tobytes()!=image.tobytes():
            raise ValueError(f'fixed bitplane vector failed:{value}')
    pattern=indexed((8,8),palette)
    pattern.putdata([x+(8 if y%2 else 0) for y in range(8) for x in range(8)])
    if encode_4bpp(pattern)!=bytes.fromhex('5533'*8+'0f000fff'*4):raise ValueError('all16color fixture failed')
    # Deliberately asymmetric corners prove H/V sharing and16x16 tile stepping.
    tile=indexed((16,16),palette)
    for x,y,value in ((0,0,1),(15,0,2),(0,15,4),(15,15,8),(5,6,15)):tile.putpixel((x,y),value)
    keys={canonical_cell(flipped(tile,h,v))[0] for h,v in ((0,0),(1,0),(0,1),(1,1))}
    if len(keys)!=1:raise ValueError('flip canonicalization fixture failed')
    sheet=indexed(SHEET_SIZE,palette);sheet.paste(tile,(112,SHEET_SIZE[1]-16))
    decoded=decode_4bpp(encode_4bpp(sheet),128,palette)
    if tile_piece(decoded,dict(tile=0xAE,hflip=False,vflip=False)).tobytes()!=tile.tobytes():
        raise ValueError('last16x16 cell fixture failed')
    # Draw-loop ASL indexing requires signed16bit offsets, while tile/props stay8bit.
    fixture = '.start_index\n  db $00\n.nbr_of_tiles\n  db $01\n.x_offsets\n  dw $FFF8, $0008\n.y_offsets\n  dw $FFE0, $0010\n.chr\n  db $00, $02\n.properties\n  db $39, $79\n.sizes\n  db $02, $02\n'
    parsed = parse_asm_tables(fixture)
    if parsed['x_offsets'] != [0xFFF8, 8] or parsed['y_offsets'] != [0xFFE0, 16]:
        raise ValueError('signed16 offset parsing fixture failed')
    rejected = fixture.replace('dw $FFF8, $0008', 'db $F8, $08')
    try:parse_asm_tables(rejected)
    except ValueError:pass
    else:raise ValueError('8bit X offset table accepted for16bit draw loop')
    try:tile_piece(decoded,dict(tile=0xB0,hflip=False,vflip=False))
    except ValueError:pass
    else:raise ValueError('out-of-bounds16x16 tile accepted')


def atomic_bytes(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def export_review(out,selected,rendered,frames,tables,validation,palette):
    out.mkdir(parents=True,exist_ok=True)
    selected['sheet'].save(out/'packed_sheet.png',transparency=0)
    try:font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Menlo.ttc',12)
    except OSError:font=ImageFont.load_default()
    board=Image.new('RGB',(4*276,((len(RUNTIME_IDS)+3)//4)*356),'#20242c');draw=ImageDraw.Draw(board)
    for index,name in enumerate(RUNTIME_IDS):
        x=index%4*276+10;y=index//4*356+24
        rgba=rendered[name].convert('RGBA').resize((256,320),Image.Resampling.NEAREST)
        board.paste(rgba,(x,y),rgba)
        draw.text((x,y-18),f'{index:02} {name} / {len(frames[name])}pieces',font=font,fill='#eadfc9')
    board.save(out/'runtime_oam_4x.png')
    names=['idle','cast_ready','cast_half','cast_a','cast_second','charge_a','charge_b',
           'throw_windup','release','throw_follow','recover_half','idle',
           'bat_up','bat_mid','bat_down','bat_mid','back_a','back_b','hurt','idle']
    gif=[]
    for name in names:
        rgba=rendered[name].convert('RGBA').resize((256,320),Image.Resampling.NEAREST)
        bg=Image.new('RGB',rgba.size,'#20242c');bg.paste(rgba,(0,0),rgba);gif.append(bg)
    gif[0].save(out/'runtime_poses.gif',save_all=True,append_images=gif[1:],duration=[180]*len(gif),loop=0,disposal=2)
    (out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    (out/'runtime_oam.json').write_text(json.dumps(dict(frames=frames,tables=tables),indent=2)+'\n')
    lines=['# Ganondorf runtime tile map','',f'Selected `{selected["name"]}` layout: **{selected["cells"]}/{MAX_CELLS}** unique16x16 cells; exact `$1800` raw4bpp sheet.',
           '', 'Body source is32x40. Local draw offsets are `x=source_x-8`, `y=source_y-16`; left uses `x=8-source_x` and toggles HFLIP.',
           'Ball source is the unchanged centered16x16 crop `(8,12)-(24,28)`, drawn at `(0,0)`. Charge reuses cast plus ball at `(0,-32)`.',
           'Each16x16 tile uses `N,N+1,N+$10,N+$11`. Base properties are `$3D` (OBJ palette6); H/V flip add `$40/$80`. Shadow owns OAM index7.', '',
           '|ID|Frame|Start|Pieces|CHR / runtime x,y / flip|','|---:|---|---:|---:|---|']
    for index,name in enumerate(RUNTIME_IDS):
        detail='; '.join(f'${p["tile"]:02X} ({p["x"]},{p["y"]}) {"H" if p["hflip"] else ""}{"V" if p["vflip"] else ""}' for p in frames[name])
        lines.append(f'|{index}|{name}|{tables["start_index"][index]}|{len(frames[name])}|{detail}|')
    lines+=['','Verification: known4bpp plane vectors, all16indices, asymmetric H/V sharing, last cell address/bounds, signed16bit X/Y table widths, source reconstruction, emittedASM table decode, runtime frame reconstruction and source hash recheck all passed.']
    (out/'TILEMAP.md').write_text('\n'.join(lines)+'\n')


def build(project_path,check=False,out=None):
    self_test()
    project,palette,images,hashes,image_path=load_source(project_path)
    candidates=[pack_layout(images,palette,False),pack_layout(images,palette,True)]
    selected=min(candidates,key=lambda item:item['cells'])
    if selected['cells']>MAX_CELLS or len(selected['binary'])!=SHEET_BYTES:
        raise ValueError(f'approved art exceeds resident sheet: {selected["cells"]}/{MAX_CELLS} cells')
    frames=runtime_maps(selected['maps'])
    asm,tables=make_asm(frames,hashes,selected)
    runtime=decode_runtime_tables(parse_asm_tables(asm))
    decoded=decode_4bpp(selected['binary'],128,palette)
    rendered={name:render_runtime(decoded,runtime[name],palette) for name in RUNTIME_IDS}
    for name,image in rendered.items():
        if image.tobytes()!=expected_runtime(name,images,palette).tobytes():raise ValueError(f'{name}: emitted runtime OAM changed pixels')
    pal=palette_binary(palette)
    if len(pal)!=32:raise ValueError('palette must be32bytes')
    outputs={ROOT/'Sprites/Bosses/ganondorf.bin':selected['binary'],
             ROOT/'Sprites/Bosses/ganondorf.pal':pal,
             ROOT/'Sprites/Bosses/ganondorf_frames.asm':asm.encode()}
    if digest(project_path.read_bytes())!=hashes['project_sha256'] or digest(image_path.read_bytes())!=hashes['canonical_sha256']:
        raise ValueError('source changed during export; no generated writes')
    if check:
        stale=[str(path.relative_to(ROOT)) for path,data in outputs.items() if not path.exists() or path.read_bytes()!=data]
        if stale:raise ValueError('stale/missing generated files: '+', '.join(stale))
    else:
        for path,data in outputs.items():atomic_bytes(path,data)
    validation=dict(result='pass',mode='check' if check else 'generate',**hashes,
        layouts={item['name']:item['cells'] for item in candidates},selected_layout=selected['name'],
        unique_16x16_cells=selected['cells'],sheet_bytes=len(selected['binary']),palette_bytes=len(pal),
        runtime_frames=len(RUNTIME_IDS),total_oam_pieces=len(tables['chr']),max_frame_pieces=max(map(len,runtime.values())),
        ordinary_max_pieces=max(len(runtime[name]) for name in RUNTIME_IDS if name not in HELD_BALL_FRAMES),
        ball_crop=[8,12,24,28],ball_runtime_offset=[0,0],charge_ball_offset=[0,-32],
        checks=['fixed4bpp_vectors','all16indices','asymmetric_flip_sharing','last_cell_bounds','signed16_offset_tables',
                'both_layout_source_reconstruction','emitted_asm_runtime_reconstruction','source_hash_recheck'],
        outputs={str(path.relative_to(ROOT)):digest(data) for path,data in outputs.items()})
    if out:export_review(out,selected,rendered,runtime,tables,validation,palette)
    return validation


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=DEFAULT_PROJECT)
    parser.add_argument('--check',action='store_true',help='Verify generated files without writing them.')
    parser.add_argument('--out',type=Path,help='Write review PNG/GIF/tilemap/validation to this directory.')
    parser.add_argument('--self-test',action='store_true',help='Run codec/flip/address fixtures only; write nothing.')
    args=parser.parse_args()
    try:
        if args.self_test:self_test();print('PASS: fixed4bpp vectors,16indices,flip sharing,last cell/bounds,signed16 offsets');return
        print(json.dumps(build(args.project.resolve(),args.check,args.out),indent=2))
    except (ValueError,OSError,KeyError,TypeError) as error:parser.exit(1,f'ERROR: {error}\n')

if __name__=='__main__':main()
