#!/usr/bin/env python3
"""
Simple dungeon room ASCII visualizer.
Cleans up z3ed dungeon-map output into readable room layouts.

Usage:
    python3 scripts/dungeon_viz.py --rom Roms/oos168x.sfc --room 0x87
    python3 scripts/dungeon_viz.py --rom Roms/oos168x.sfc --d6
    python3 scripts/dungeon_viz.py --overview
"""
import argparse, json, os, subprocess, sys
PLAIN = False
SCALE = 3

D6 = [0x77,0x78,0x79,0x87,0x88,0x89,0x97,0x98,0x99,
      0xA8,0xA9,0xB8,0xB9,0xC8,0xD7,0xD8,0xD9,0xDA]

NAMES = {
    0x77:'NW Hall',0x78:'Miniboss',0x79:'NE Hall',
    0x87:'West Hall',0x88:'Big Chest',0x89:'East Hall',
    0x97:'SW Hall',0x98:'Entrance',0x99:'SE Hall',
    0xA8:'B1 Switch',0xA9:'B1 Rest',0xB8:'B1 Fork',0xB9:'B1 Maze',
    0xC8:'Boss',0xD7:'B2 West',0xD8:'Pre-Boss',0xD9:'B2 Crumble',0xDA:'B2 Stage',
}

def z3ed_path():
    d = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(d,'..','..','yaze','scripts','z3ed')
    return os.path.abspath(p) if os.path.exists(p) else 'z3ed'

def get_map(rom, room_id):
    try:
        r = subprocess.run([z3ed_path(),'dungeon-map',
            f'--room=0x{room_id:02X}',f'--rom={rom}'],
            capture_output=True, text=True, timeout=10)
        d = json.loads(r.stdout).get('dungeon_map',{})
        return d.get('map',[])
    except:
        return []

def clean(ch):
    """Map z3ed char to clean ASCII."""
    if ch == '#': return '#'
    if ch == 'D': return 'D'
    if ch == 'v': return 'v'
    if ch == '>': return '>'
    if ch == 'C': return 'C'
    if ch == 'S': return 'S'
    if ch == 'B': return 'B'
    if ch == 'X': return 'x'
    if ch == 'T': return 'T'
    if ch in ('~','-'): return '-'
    if ch == '|': return '|'
    if ch == '+': return '+'
    if ch in ('N','s','E','W'): return ch  # stop tiles
    return ' '

def color(ch):
    if PLAIN: return ch
    if ch == '#': return f'\033[2m{ch}\033[0m'
    if ch == 'D': return f'\033[93m{ch}\033[0m'
    if ch == 'v': return f'\033[91m{ch}\033[0m'
    if ch == '>': return f'\033[92m{ch}\033[0m'
    if ch == 'C': return f'\033[93;1m{ch}\033[0m'
    if ch == 'S': return f'\033[95m{ch}\033[0m'
    if ch == 'B': return f'\033[97m{ch}\033[0m'
    if ch == 'x': return f'\033[91m{ch}\033[0m'
    if ch == 'T': return f'\033[93m{ch}\033[0m'
    if ch in ('-','|','+'): return f'\033[96m{ch}\033[0m'
    if ch in ('N','s','E','W'): return f'\033[92;1m{ch}\033[0m'
    return ' '

def render(rom, room_id, show_coords=False):
    name = NAMES.get(room_id, f'0x{room_id:02X}')
    lines = get_map(rom, room_id)
    if not lines:
        print(f'  0x{room_id:02X} {name} — no data')
        return

    # Parse and clean into a 2D grid.
    # grid[0] is the column-header row from dungeon-map (all spaces after clean).
    # grid[i] for i >= 1 corresponds to actual tile row (i - 1).
    grid = []
    for line in lines:
        parts = line.split(None, 1)
        if len(parts) < 2: continue
        try: int(parts[0])
        except ValueError: continue
        grid.append([clean(ch) for ch in parts[1]])

    if not grid:
        return

    h = len(grid)
    w = max(len(r) for r in grid) if grid else 0
    # Pad rows to uniform width
    for r in grid:
        while len(r) < w: r.append(' ')

    def interesting(ch):
        return ch not in (' ', '#')

    # Crop to bounding box of interesting content, keep 1 wall border
    top = next((r for r in range(h) if any(interesting(grid[r][c]) for c in range(w))), 0)
    bot = next((r for r in range(h-1,-1,-1) if any(interesting(grid[r][c]) for c in range(w))), h-1)
    left = next((c for c in range(w) if any(interesting(grid[r][c]) for r in range(h))), 0)
    right = next((c for c in range(w-1,-1,-1) if any(interesting(grid[r][c]) for r in range(h))), w-1)
    top = max(0, top - 1)
    bot = min(h - 1, bot + 1)
    left = max(0, left - 1)
    right = min(w - 1, right + 1)

    # Downsample NxN — pick the most interesting char from each block
    s = SCALE
    compact = []
    for r in range(top, bot + 1, s):
        row = []
        for c in range(left, right + 1, s):
            chars = []
            for dr in range(s):
                for dc in range(s):
                    rr, cc = r + dr, c + dc
                    if rr <= bot and cc <= right:
                        chars.append(grid[rr][cc])
            pick = ' '
            for ch in chars:
                if interesting(ch): pick = ch; break
                if ch == '#': pick = '#'
            row.append(pick)
        compact.append(row)

    # Strip trailing empty columns
    for row in compact:
        while row and row[-1] == ' ':
            row.pop()

    # Strip common leading wall/space columns.
    # Track how many columns were trimmed so we can recover actual tile coords.
    trim = 0
    if compact:
        min_lead = min((next((i for i, ch in enumerate(r) if interesting(ch)), len(r)) for r in compact if r), default=0)
        if min_lead > 1:
            trim = min_lead - 1  # keep 1 wall column
            compact = [r[trim:] for r in compact]

    # actual tile col of display column c: col_base + c * s
    col_base = left + trim * s

    # Collapse consecutive blank/wall-only rows to at most 1.
    # Also track the original compact row index for each kept row so we can
    # recover the actual tile row: actual_row = (top + compact_idx * s) - 1
    # (the -1 corrects for the all-spaces header row that dungeon-map prepends).
    def row_is_boring(r):
        return all(ch in (' ', '#') for ch in r)

    filtered = []
    compact_indices = []  # original compact row index for each filtered row
    prev_boring = False
    for i, row in enumerate(compact):
        if not row: continue
        boring = row_is_boring(row)
        if boring and prev_boring:
            continue  # skip consecutive boring rows
        filtered.append(row)
        compact_indices.append(i)
        prev_boring = boring

    hdr = f'  0x{room_id:02X} {name}'
    print(hdr if PLAIN else f'\033[1m{hdr}\033[0m')

    if show_coords and filtered:
        max_w = max(len(r) for r in filtered)
        # Two-line column header: tens digit (at multiples of 10) and units digit.
        pad = '      '  # 6 chars to align with '  NNN ' row label
        tens = pad
        units = pad
        for c in range(max_w):
            col = col_base + c * s
            tens += str(col // 10) if col % 10 == 0 else ' '
            units += str(col % 10)
        dim = '' if PLAIN else '\033[2m'
        rst = '' if PLAIN else '\033[0m'
        print(f'{dim}{tens}{rst}')
        print(f'{dim}{units}{rst}')
        for i, row in enumerate(filtered):
            actual_row = max(0, (top + compact_indices[i] * s) - 1)
            lbl = f'{dim}{actual_row:3d} {rst}'
            print('  ' + lbl + ''.join(color(ch) for ch in row))
    else:
        for row in filtered:
            print('  ' + ''.join(color(ch) for ch in row))
    print()

def overview():
    print()
    print('\033[1m  D6 GORON MINES\033[0m')
    print()
    print('  \033[1mF1\033[0m  ┌──────┬──────┬──────┐')
    print('      │ \033[94m77\033[0m NW│ \033[91m78\033[0m Mi│ \033[91m79\033[0m NE│')
    print('      ├──────┼──────┼──────┤')
    print('      │ \033[92m87\033[0m We│ \033[92m88\033[0m Ch│ \033[94m89\033[0m Ea│')
    print('      ├──────┼──────┼──────┤')
    print('      │ \033[94m97\033[0m SW│ \033[92m98\033[0m ★ │ \033[2m99\033[0m SE│')
    print('      └──────┴──┬───┴──────┘')
    print('         stairs ↓       ↓ holewarp')
    print('  \033[1mB1\033[0m  ┌──────┬──────┐')
    print('      │ \033[94mA8\033[0m Sw│ \033[2mA9\033[0m   │')
    print('      ├──────┼──────┤')
    print('      │ \033[91mB8\033[0m Fk│ \033[94mB9\033[0m Mz│')
    print('      └──────┴──┬───┘')
    print('             drop ↓')
    print('  \033[1mB2\033[0m  ┌──────┬──────┬──────┬──────┐')
    print('      │ \033[94mD7\033[0m Rv│ \033[93mD8\033[0m PB│ \033[93mD9\033[0m Cr│ \033[94mDA\033[0m St│')
    print('      └──────┴──┬───┴──────┴──────┘')
    print('             ┌──┴───┐')
    print('             │ \033[91mC8\033[0m Bo│')
    print('             └──────┘')
    print()
    print('  \033[92m██\033[0m active  \033[94m██\033[0m planned  \033[91m██\033[0m blocked  \033[93m██\033[0m priority')
    print()
    print('  # wall  D door  v pit  > stair  C chest  S switch')
    print('  \033[96m- | +\033[0m track   \033[92;1mN s E W\033[0m stop tiles   x spike  B block')
    print()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom')
    ap.add_argument('--room')
    ap.add_argument('--rooms')
    ap.add_argument('--d6', action='store_true')
    ap.add_argument('--overview', action='store_true')
    ap.add_argument('--plain', action='store_true', help='no ANSI colors')
    ap.add_argument('--scale', type=int, default=3, help='downsample factor (default 3)')
    ap.add_argument('--coords', action='store_true', help='show tile row/col coordinates')
    a = ap.parse_args()
    global PLAIN, SCALE
    PLAIN = a.plain
    SCALE = a.scale

    if a.overview or (not a.rom and not a.room and not a.rooms and not a.d6):
        overview()
        if not a.rom: return

    if not a.rom:
        ap.error('--rom required')

    if a.d6:
        overview()
        for r in D6: render(a.rom, r, show_coords=a.coords)
    elif a.rooms:
        for r in a.rooms.split(','): render(a.rom, int(r.strip(),16), show_coords=a.coords)
    elif a.room:
        render(a.rom, int(a.room,16), show_coords=a.coords)

if __name__ == '__main__':
    main()
