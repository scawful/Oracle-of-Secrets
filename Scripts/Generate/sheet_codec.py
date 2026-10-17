#!/usr/bin/env python3
"""3bpp sprite sheet <-> 128x32 index grid <-> text grid / indexed PNG.

Sheet layout (decompressed, 0x600 bytes): 64 tiles x 24 bytes, 16 tiles per row.
Tile: rows 0-7 as (bp0, bp1) byte pairs (16 bytes), then 8 bytes bp2. Bit 7 = left.
Sprite char c in a slot uses tile c & $3F; a 16x16 OBJ at N uses N, N+1, N+16, N+17.
Text grid: 32 lines x 128 chars, '.' = 0, '1'-'7' = colour index (git-diffable).
"""
import struct
import zlib

W, H = 128, 32

def sheet_to_grid(d):
    if len(d) != 0x600:
        raise ValueError('need exactly 1536 decoded sheet bytes')
    g = [[0] * W for _ in range(H)]
    for t in range(64):
        base = t * 24; tx, ty = (t % 16) * 8, (t // 16) * 8
        for y in range(8):
            p0, p1, p2 = d[base + 2*y], d[base + 2*y + 1], d[base + 16 + y]
            for x in range(8):
                b = 7 - x
                g[ty+y][tx+x] = ((p0 >> b) & 1) | (((p1 >> b) & 1) << 1) | (((p2 >> b) & 1) << 2)
    return g

def grid_to_sheet(g):
    if len(g) != H or any(len(row) != W for row in g):
        raise ValueError('need 32 rows of 128 indices')
    out = bytearray(0x600)
    for t in range(64):
        base = t * 24; tx, ty = (t % 16) * 8, (t // 16) * 8
        for y in range(8):
            p0 = p1 = p2 = 0
            for x in range(8):
                v = g[ty+y][tx+x]
                if type(v) is not int or not 0 <= v <= 7:
                    raise ValueError('indices must be integers 0-7')
                b = 0x80 >> x
                if v & 1: p0 |= b
                if v & 2: p1 |= b
                if v & 4: p2 |= b
            out[base + 2*y], out[base + 2*y + 1], out[base + 16 + y] = p0, p1, p2
    return bytes(out)

def grid_to_text(g):
    return '\n'.join(''.join('.' if v == 0 else str(v) for v in row) for row in g) + '\n'

def text_to_grid(s):
    rows = [r for r in s.splitlines() if r and not r.startswith('#')]
    if len(rows) != H or any(len(r) != W for r in rows) or any(c not in '.01234567' for r in rows for c in r):
        raise ValueError('need 32 rows of 128 indices (. or 0-7)')
    return [[0 if c == '.' else int(c) for c in r] for r in rows]

def png_to_grid(path):
    """Read 8-bit indexed, noninterlaced PNG without a build dependency on Pillow."""
    from pathlib import Path
    data = Path(path).read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('invalid PNG signature')
    p = 8; compressed = bytearray(); header = None; palette = None; ended = False
    while p < len(data):
        if p + 12 > len(data):
            raise ValueError('truncated PNG chunk')
        size = int.from_bytes(data[p:p+4], 'big'); kind = data[p+4:p+8]
        payload = data[p+8:p+8+size]; end = p + size + 12
        if end > len(data) or zlib.crc32(kind+payload) != int.from_bytes(data[end-4:end], 'big'):
            raise ValueError('invalid PNG chunk length or CRC')
        if header is None and kind != b'IHDR':
            raise ValueError('PNG must begin with IHDR')
        if kind == b'IHDR':
            if header is not None or size != 13:
                raise ValueError('invalid PNG header')
            header = struct.unpack('>IIBBBBB', payload)
            if header != (W, H, 8, 3, 0, 0, 0):
                raise ValueError('need 8-bit indexed noninterlaced 128x32 PNG')
        elif kind == b'PLTE':
            palette = payload
        elif kind == b'IDAT':
            if palette is None:
                raise ValueError('indexed PNG needs a palette before pixel data')
            compressed.extend(payload)
        elif kind == b'IEND':
            if size or end != len(data):
                raise ValueError('invalid PNG end')
            ended = True; break
        elif not kind[0] & 32:
            raise ValueError('unsupported critical PNG chunk')
        p = end
    if not ended or palette is None or len(palette) % 3 or not 24 <= len(palette) <= 768:
        raise ValueError('incomplete indexed PNG')
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(compressed, (W+1)*H+1)
    if len(pixels) != (W+1)*H or not decoder.eof or decoder.unused_data:
        raise ValueError('invalid PNG pixel length')
    grid = []; prior = bytes(W)
    def paeth(a,b,c):
        value=a+b-c; distances=(abs(value-a),abs(value-b),abs(value-c))
        return (a,b,c)[distances.index(min(distances))]
    for y in range(H):
        kind = pixels[y*(W+1)]; row = bytearray(pixels[y*(W+1)+1:(y+1)*(W+1)])
        if kind > 4:
            raise ValueError('invalid PNG row filter')
        for x in range(W):
            left=row[x-1] if x else 0; up=prior[x]; corner=prior[x-1] if x else 0
            predictor=(0,left,up,(left+up)//2,paeth(left,up,corner))[kind]
            row[x]=(row[x]+predictor)&255
        if any(v > 7 for v in row):
            raise ValueError('indices must be 0-7')
        grid.append(list(row)); prior=row
    return grid

def grid_to_png(g, path, palette=None, scale=1):
    from PIL import Image
    pal = palette or [(i * 36, i * 36, i * 36) for i in range(8)]
    im = Image.new('P', (W, H)); im.putpalette([c for rgb in pal for c in rgb] + [0] * (768 - 24))
    im.putdata([v for r in g for v in r])
    if scale > 1: im = im.resize((W * scale, H * scale), Image.NEAREST)
    im.save(path)

def paste_cell(g, char, rows):
    """Paste a 16x16 (16 rows) or 8x8 (8 rows) hex/'.' grid at sheet char & $3F."""
    t = char & 0x3F; tx, ty = (t % 16) * 8, (t // 16) * 8
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            g[ty+y][tx+x] = 0 if c == '.' else int(c, 16)
