#!/usr/bin/env python3
"""Build SNES 4bpp sprite tiles from a pixels.txt grid (stdlib only).

Usage: pixels_to_4bpp.py Sprites/NPCs/gfx/farore_reach.txt Sprites/NPCs/gfx/farore_reach.bin [--runs] [--check]

Input format (one or more blocks, in output order):

    # comment
    cell CE 16x16
    ....55555.......
    (16 rows of 16 chars)
    cell F1 8x8
    (8 rows of 8 chars)

Each pixel is a colour index 0-7 ('.' = 0 = transparent). Indices 1-7 render
with OBJ palette colours 1-7 because plane 3 is written as 0, which is what
the vanilla Do3To4Low16Bit ($00:DFB8) does for every sprite sheet that is not
in the "high" list ($52/$53/$5A/$5B for slot 3). Sheet $55 is low.

Output: for each block, its tiles as 32-byte 4bpp tiles.
  - 16x16 at char N: run 1 = tiles N, N+1 (64 bytes, top half),
                     run 2 = tiles N+$10, N+$11 (64 bytes, bottom half).
  - 8x8 at char N:   run = tile N (32 bytes).
The runs are concatenated in file order. --runs prints each run's offset in
the .bin, its offset in the $7F0000 sprite upload buffer for a given slot,
and its length, so the ASM copy loop can be checked against it.

4bpp tile (32 bytes): row r -> byte 2r = plane 0, 2r+1 = plane 1,
16+2r = plane 2, 17+2r = plane 3 (always 0 here). Bit 7 = leftmost pixel.
"""
import argparse
import sys


def parse(path):
    blocks, cur = [], None
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    for ln, raw in enumerate(lines, 1):
        line = raw.split('#', 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith('cell '):
            parts = line.split()
            if len(parts) != 3 or parts[2] not in ('16x16', '8x8'):
                sys.exit(f'{path}:{ln}: expected "cell <hex char> 16x16|8x8"')
            size = 16 if parts[2] == '16x16' else 8
            cur = {'char': int(parts[1], 16), 'size': size, 'rows': [], 'line': ln}
            blocks.append(cur)
            continue
        if cur is None:
            sys.exit(f'{path}:{ln}: pixel row before the first "cell" line')
        row = line.strip()
        if len(row) != cur['size']:
            sys.exit(f'{path}:{ln}: row has {len(row)} pixels, cell is {cur["size"]} wide')
        vals = []
        for ch in row:
            v = 0 if ch == '.' else (int(ch) if ch.isdigit() else -1)
            if not 0 <= v <= 7:
                sys.exit(f'{path}:{ln}: pixel {ch!r} is not 0-7 or "."')
            vals.append(v)
        cur['rows'].append(vals)
    for b in blocks:
        if len(b['rows']) != b['size']:
            sys.exit(f'{path}:{b["line"]}: cell ${b["char"]:02X} has {len(b["rows"])} rows, needs {b["size"]}')
    return blocks


def tile_4bpp(px, ox, oy):
    """px: 2D list of indices 0-7. Returns 32 bytes for the 8x8 tile at (ox, oy)."""
    out = bytearray(32)
    for r in range(8):
        p = [0, 0, 0]
        for c in range(8):
            v = px[oy + r][ox + c]
            for plane in range(3):
                if v >> plane & 1:
                    p[plane] |= 0x80 >> c
        out[2 * r], out[2 * r + 1], out[16 + 2 * r] = p[0], p[1], p[2]
        # out[17 + 2r] = plane 3 = 0 (low conversion)
    return bytes(out)


def build(blocks):
    data, runs = bytearray(), []
    for b in blocks:
        n, px = b['char'], b['rows']
        if b['size'] == 16:
            if (n & 0x0F) == 0x0F:
                sys.exit(f'cell ${n:02X}: a 16x16 OBJ cannot start in column $F')
            halves = [(n, tile_4bpp(px, 0, 0) + tile_4bpp(px, 8, 0)),
                      ((n + 0x10) & 0xFF, tile_4bpp(px, 0, 8) + tile_4bpp(px, 8, 8))]
        else:
            halves = [(n, tile_4bpp(px, 0, 0))]
        for ch, chunk in halves:
            runs.append((len(data), ch, len(chunk)))
            data += chunk
    return bytes(data), runs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('pixels')
    ap.add_argument('out', nargs='?', help='write the .bin here')
    ap.add_argument('--check', action='store_true', help='fail if OUT differs from a fresh build')
    ap.add_argument('--runs', action='store_true', help='print the copy runs')
    ap.add_argument('--slot', type=int, default=3, help='sprite slot of the sheet (default 3)')
    a = ap.parse_args()
    data, runs = build(parse(a.pixels))
    if a.runs:
        for off, ch, ln in runs:
            buf = a.slot * 0x800 + (ch & 0x3F) * 0x20
            print(f'bin +${off:03X} -> $7F{buf:04X} (char ${ch:02X}, VRAM word ${0x5000 + buf // 2:04X}) {ln} bytes')
    if a.out:
        if a.check:
            with open(a.out, 'rb') as f:
                old = f.read()
            if old != data:
                sys.exit(f'{a.out} is stale: rebuild with {sys.argv[0]} {a.pixels} {a.out}')
            print(f'{a.out}: up to date ({len(data)} bytes)')
        else:
            with open(a.out, 'wb') as f:
                f.write(data)
            print(f'wrote {a.out} ({len(data)} bytes)')


if __name__ == '__main__':
    main()
