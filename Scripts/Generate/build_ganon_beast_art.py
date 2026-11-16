#!/usr/bin/env python3
"""Pack the Ganon beast (final form) art into one SNES 4bpp sheet.

Source: Data/graphics/ganon_beast/{canonical.png,project.json}.
Generated: Sprites/Bosses/{ganon_beast.bin,ganon_beast.pal,ganon_beast_frames.asm}.
16x16 cells are deduplicated across h/v flips. Cells $6A/$6C/$6E/$80/$82 are
copied from ganondorf.bin so Ganondorf's energy balls and bats still draw if
alive when the beast sheet replaces his. No ROM is read or written.
Usage: build_ganon_beast_art.py [--check] [--preview PNG]
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'Data/graphics/ganon_beast'
OUT_BIN = ROOT / 'Sprites/Bosses/ganon_beast.bin'
OUT_PAL = ROOT / 'Sprites/Bosses/ganon_beast.pal'
OUT_ASM = ROOT / 'Sprites/Bosses/ganon_beast_frames.asm'
GANONDORF_BIN = ROOT / 'Sprites/Bosses/ganondorf.bin'
SHEET_W, SHEET_H, CELLS = 128, 96, 48
BASE_PROPERTIES = 0x3D  # OBJ palette 6, priority 3, second name table
BODY = ('idle', 'roar', 'core_open', 'cloak', 'trident_up')
TRIDENT = ('trident_v', 'trident_h')
MAX_BODY = 12     # OAM entries 0-11 (ganon_beast.asm)
MAX_TRIDENT = 2   # OAM entries 12-13


def cell_chr(cell):
    return (cell % 8) * 2 + (cell // 8) * 0x20


def chr_cell(chr_):
    return (chr_ & 0x0F) // 2 + (chr_ >> 5) * 8


def encode_4bpp(image):
    px = image.tobytes()
    out = bytearray()
    for top in range(0, image.height, 8):
        for left in range(0, image.width, 8):
            tile = bytearray(32)
            for y in range(8):
                for x in range(8):
                    v = px[(top + y) * image.width + left + x]
                    for plane in range(4):
                        tile[(plane // 2) * 16 + y * 2 + plane % 2] |= ((v >> plane) & 1) << (7 - x)
            out += tile
    return bytes(out)


def decode_4bpp(data, width):
    tiles_w = width // 8
    height = len(data) // 32 // tiles_w * 8
    px = bytearray(width * height)
    for t in range(len(data) // 32):
        left, top = t % tiles_w * 8, t // tiles_w * 8
        tile = data[t * 32:t * 32 + 32]
        for y in range(8):
            for x in range(8):
                px[(top + y) * width + left + x] = sum(
                    ((tile[(p // 2) * 16 + y * 2 + p % 2] >> (7 - x)) & 1) << p for p in range(4))
    return Image.frombytes('P', (width, height), bytes(px))


def flip(img, h, v):
    if h:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if v:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return img


def load():
    project = json.loads((SRC / 'project.json').read_text())
    image = Image.open(SRC / project['image'])
    image.load()
    if image.mode != 'P' or max(image.tobytes()) > 15:
        raise ValueError('canonical.png must be indexed, indexes 0..15')
    words = [int(w.lstrip('$'), 16) for w in project['palette_bgr555']]
    if len(words) != 16:
        raise ValueError('16 palette words required')
    frames = {f['id']: f for f in project['frames']}
    missing = set(BODY + TRIDENT) - set(frames)
    if missing:
        raise ValueError(f'missing frames {sorted(missing)}')
    return project, image, words, frames


def pack(image, frames):
    reserved = {chr_cell(c) for c in (0x6A, 0x6C, 0x6E, 0x80, 0x82)}
    free = [c for c in range(CELLS) if c not in reserved]
    stored = []          # list of (cell index, image)
    keys = {}            # bytes -> (stored idx, h, v)
    pieces = {}
    for name in BODY + TRIDENT:
        x0, y0, w, h = frames[name]['rect']
        out = []
        for cy in range(h // 16):
            for cx in range(w // 16):
                cell = image.crop((x0 + cx * 16, y0 + cy * 16, x0 + cx * 16 + 16, y0 + cy * 16 + 16))
                if not any(cell.tobytes()):
                    continue
                hit = None
                for hf in (False, True):
                    for vf in (False, True):
                        k = flip(cell, hf, vf).tobytes()
                        if k in keys and hit is None:
                            idx, h0, v0 = keys[k]
                            hit = (idx, h0 ^ hf, v0 ^ vf)
                if hit is None:
                    if not free:
                        raise ValueError('more than 43 unique cells')
                    idx = len(stored)
                    stored.append((free.pop(0), cell))
                    keys[cell.tobytes()] = (idx, False, False)
                    hit = (idx, False, False)
                idx, hf, vf = hit
                # anchor: sprite X+8 = horizontal centre; body feet at Y+16, trident centred on Y+8
                px = cx * 16 - w // 2 + 8
                py = cy * 16 - (h - 16) if name in BODY else cy * 16 - h // 2 + 8
                out.append(dict(cell=stored[idx][0], x=px, y=py, hflip=hf, vflip=vf))
        limit = MAX_BODY if name in BODY else MAX_TRIDENT
        if len(out) > limit:
            raise ValueError(f'{name}: {len(out)} pieces > {limit}')
        pieces[name] = out
    return stored, reserved, pieces


def make_sheet(stored, reserved):
    sheet = Image.new('P', (SHEET_W, SHEET_H), 0)
    for cell, img in stored:
        sheet.paste(img, ((cell % 8) * 16, (cell // 8) * 16))
    gd = decode_4bpp(GANONDORF_BIN.read_bytes(), SHEET_W)
    for cell in reserved:
        box = ((cell % 8) * 16, (cell // 8) * 16, (cell % 8) * 16 + 16, (cell // 8) * 16 + 16)
        sheet.paste(gd.crop(box), box[:2])
    return sheet


def make_asm(pieces, canon_sha, n_unique):
    order = BODY + TRIDENT
    t = {k: [] for k in ('start', 'count', 'x', 'y', 'chr', 'props', 'sizes')}
    for name in order:
        t['start'].append(len(t['chr']))
        t['count'].append(len(pieces[name]) - 1)
        for p in pieces[name]:
            t['x'].append(p['x'] & 0xFFFF)
            t['y'].append(p['y'] & 0xFFFF)
            t['chr'].append(cell_chr(p['cell']))
            t['props'].append(BASE_PROPERTIES | (0x40 if p['hflip'] else 0) | (0x80 if p['vflip'] else 0))
            t['sizes'].append(2)

    def rows(vals, fmt, kw):
        return '\n'.join(f'  {kw} ' + ', '.join(fmt % v for v in vals[i:i + 16])
                         for i in range(0, len(vals), 16))
    head = [
        '; Generated by Scripts/Generate/build_ganon_beast_art.py; do not edit.',
        '; Stand-in GBC art (reference recolour), OBJ palette 6, second name table.',
        f'; Canonical SHA256: {canon_sha}',
        f'; {n_unique} unique 16x16 cells + 5 cells copied from ganondorf.bin ($6A $6C $6E $80 $82).',
        '; Frames: ' + ', '.join(f'{i}={n}' for i, n in enumerate(order)),
        '; Body: X+8 = centre, feet at Y+16. Trident: centred on (X+8, Y+8).',
        '; X/Y offsets are signed 16-bit dw; other tables db. nbr_of_tiles = pieces - 1.',
        '',
    ]
    for i, n in enumerate(order):
        head.append(f'!BeastFrame_{n} = {i}')
    head += [
        '',
        '.start_index', rows(t['start'], '$%02X', 'db'),
        '.nbr_of_tiles', rows(t['count'], '$%02X', 'db'),
        '.x_offsets', rows(t['x'], '$%04X', 'dw'),
        '.y_offsets', rows(t['y'], '$%04X', 'dw'),
        '.chr', rows(t['chr'], '$%02X', 'db'),
        '.properties', rows(t['props'], '$%02X', 'db'),
        '.sizes', rows(t['sizes'], '$%02X', 'db'),
    ]
    return '\n'.join(head) + '\n', t


def render(sheet_bin, t, idx, palette):
    sheet = decode_4bpp(sheet_bin, SHEET_W)
    canvas = Image.new('P', (96, 96), 0)
    s, n = t['start'][idx], t['count'][idx] + 1
    for k in range(s, s + n):
        c = t['chr'][k]
        cell = sheet.crop(((c & 0x0F) * 8, (c >> 4) * 8, (c & 0x0F) * 8 + 16, (c >> 4) * 8 + 16))
        cell = flip(cell, bool(t['props'][k] & 0x40), bool(t['props'][k] & 0x80))
        sx = t['x'][k] - 0x10000 if t['x'][k] >= 0x8000 else t['x'][k]
        sy = t['y'][k] - 0x10000 if t['y'][k] >= 0x8000 else t['y'][k]
        mask = cell.point(lambda v: 255 if v else 0, 'L')
        canvas.paste(cell, (40 + sx, 64 + sy), mask)
    canvas.putpalette(palette)
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='fail if outputs differ')
    ap.add_argument('--preview', type=Path)
    a = ap.parse_args()
    project, image, words, frames = load()
    stored, reserved, pieces = pack(image, frames)
    sheet = make_sheet(stored, reserved)
    sheet_bin = encode_4bpp(sheet)
    assert len(sheet_bin) == 0x1800
    pal = b''.join(w.to_bytes(2, 'little') for w in words)
    canon_sha = hashlib.sha256((SRC / project['image']).read_bytes()).hexdigest()
    asm, t = make_asm(pieces, canon_sha, len(stored))
    rgb = []
    for w in words:
        rgb += [(w & 31) << 3, ((w >> 5) & 31) << 3, ((w >> 10) & 31) << 3]
    rgb += [0] * (768 - len(rgb))
    # round trip: every frame rendered from the emitted sheet+tables equals the source crop
    for i, name in enumerate(BODY + TRIDENT):
        x0, y0, w, h = frames[name]['rect']
        got = render(sheet_bin, t, i, rgb)
        ox = 40 - w // 2 + 8
        oy = 64 - (h - 16) if name in BODY else 64 - h // 2 + 8
        if got.crop((ox, oy, ox + w, oy + h)).tobytes() != image.crop((x0, y0, x0 + w, y0 + h)).tobytes():
            raise SystemExit(f'round trip failed: {name}')
    outs = {OUT_BIN: sheet_bin, OUT_PAL: pal, OUT_ASM: asm.encode()}
    if a.check:
        bad = [str(p) for p, d in outs.items() if not p.exists() or p.read_bytes() != d]
        if bad:
            raise SystemExit('stale: ' + ', '.join(bad))
    else:
        for p, d in outs.items():
            p.write_bytes(d)
    if a.preview:
        def rgba(img):
            img.info['transparency'] = 0
            return img.convert('RGBA')
        tiles = [rgba(render(sheet_bin, t, i, rgb)) for i in range(len(BODY + TRIDENT))]
        sh = sheet.copy()
        sh.putpalette(rgb)
        sh = rgba(sh)
        out = Image.new('RGBA', (96 * len(tiles), 96 + 8 + SHEET_H), (22, 24, 29, 255))
        for i, tile in enumerate(tiles):
            out.alpha_composite(tile, (i * 96, 0))
        out.alpha_composite(sh, (0, 104))
        out.resize((out.width * 4, out.height * 4), Image.NEAREST).save(a.preview)
    print(f'cells {len(stored)}+5 reserved; pieces ' +
          ', '.join(f'{n}={len(pieces[n])}' for n in BODY + TRIDENT))


if __name__ == '__main__':
    sys.exit(main())
