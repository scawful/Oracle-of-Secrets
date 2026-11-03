#!/usr/bin/env python3
"""Place labelled 8x8 tiles at sheet indices whose VRAM tile type fits (Pillow; no ROM access).

A tile's behavior belongs to its VRAM char: char = slot * $40 + index. Each tile goes to a free
index whose type is in the tile's type set for every target slot (and dungeon blockset), or the
run stops with exit 2 and a capacity report. Validation errors exit 1. Inputs are never written.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
CODEC = HERE.parent / 'Generate' / 'sheet_codec.py'
DEFAULT_CLASSES = HERE / 'tile_type_classes.json'
SPEC_KEYS = {'schema', 'world', 'slots', 'blocksets', 'source', 'base_sheet', 'free', 'dedupe_flips', 'tiles'}
TILE_KEYS = {'id', 'cell', 'class', 'types', 'index'}
# Frame colours from tile_type_slot_map_2026-10-25/render_slot_types.py CAT, keyed by class name.
COLORS = {'floor': (236, 232, 220), 'solid': (90, 90, 96), 'deep_water': (40, 90, 200),
          'shallow_water': (120, 170, 240), 'pit': (20, 20, 20), 'ledge': (240, 150, 40),
          'slope': (200, 170, 120), 'stairs': (150, 90, 200), 'hookable': (140, 90, 50),
          'grass_bush_rock': (70, 160, 70), 'ice': (120, 230, 230), 'spike': (210, 50, 50)}
OTHER = (220, 80, 200)
SCALE = 4
# Node limit for the exact fallback search; past it the run reports unplaced with search='exhausted'.
SEARCH_BUDGET = 20000


def integer(value):
    return type(value) is int


def sheet_codec():
    spec = importlib.util.spec_from_file_location('sheet_codec', CODEC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def type_list(value, count, name):
    if not isinstance(value, list) or len(value) != count or any(not integer(v) or not 0 <= v <= 255 for v in value):
        raise ValueError(f'{name} must be {count} integers 0-255')
    return value


def load_types(path):
    """Read slot_types.json schema 1 (DESIGN.md section 3, including the $140-$1BF null correction)."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or data.get('schema') != 1:
        raise ValueError('slot types file must be schema 1')
    type_list(data.get('overworld'), 512, 'overworld')
    shared = data.get('dungeon_shared')
    if not isinstance(shared, list) or len(shared) != 512:
        raise ValueError('dungeon_shared must have 512 entries')
    # $0E:9659 is $180 bytes; chars $140-$1BF come only from the blockset overlay and are null here.
    type_list(shared[:0x140] + shared[0x1C0:], 0x180, 'dungeon_shared outside $140-$1BF')
    if any(v is not None for v in shared[0x140:0x1C0]):
        raise ValueError('dungeon_shared must be null at chars $140-$1BF (blockset overlay)')
    blocksets = data.get('dungeon_blocksets')
    if not isinstance(blocksets, dict):
        raise ValueError('dungeon_blocksets must be an object')
    for key, value in blocksets.items():
        if not key.isdigit() or str(int(key)) != key:
            raise ValueError('dungeon_blocksets keys must be decimal blockset numbers')
        type_list(value, 128, f'dungeon_blocksets[{key}]')
    return data


def load_classes(path):
    """Read tile_type_classes.json schema 1 (DESIGN.md section 4)."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('classes'), dict):
        raise ValueError('classes file must be schema 1 with a classes object')
    classes = {}
    for name, ids in data['classes'].items():
        if not isinstance(ids, list) or not ids or any(not integer(v) or not 0 <= v <= 255 for v in ids):
            raise ValueError(f'class {name} must list type IDs 0-255')
        classes[name] = sorted(set(ids))
    return classes


def contexts(types, world, slots, blocksets):
    """Return [(slot, blockset|None, [64 types])] for every slot x blockset the sheet must fit."""
    out = []
    for slot in slots:
        base = slot * 0x40
        if world == 'overworld':
            out.append((slot, None, types['overworld'][base:base + 64]))
        elif slot in (5, 6):
            for blockset in blocksets:
                group = types['dungeon_blocksets'].get(str(blockset))
                if group is None:
                    raise ValueError(f'blockset {blockset} missing from slot types file')
                out.append((slot, blockset, group[base - 0x140:base - 0x140 + 64]))
        else:
            out.append((slot, None, types['dungeon_shared'][base:base + 64]))
    return out


def read_source(path):
    with Image.open(path) as image:
        if image.mode != 'P':
            raise ValueError('source must be a mode-P (indexed) PNG')
        width, height = image.size
        if not width or not height or width % 8 or height % 8:
            raise ValueError('source width and height must be nonzero multiples of 8')
        pixels = list(image.tobytes())
        palette = image.getpalette()
    if any(v > 7 for v in pixels):
        raise ValueError('source pixel values must be 0-7 (3bpp)')
    return [pixels[y * width:(y + 1) * width] for y in range(height)], palette


def read_base(path, codec):
    path = Path(path)
    if path.suffix.lower() == '.bin':
        raw = path.read_bytes()
        if len(raw) != 0x600:
            raise ValueError('base_sheet .bin must be 0x600 bytes')
        return codec.sheet_to_grid(raw), None
    if path.suffix.lower() != '.png':
        raise ValueError('base_sheet must be .png or .bin')
    with Image.open(path) as image:
        if image.mode != 'P' or image.size != (codec.W, codec.H):
            raise ValueError('base_sheet PNG must be 128x32 mode P')
        pixels = list(image.tobytes())
        palette = image.getpalette()
    if any(v > 7 for v in pixels):
        raise ValueError('base_sheet pixel values must be 0-7 (3bpp)')
    return [pixels[y * codec.W:(y + 1) * codec.W] for y in range(codec.H)], palette


def tile_at(grid, tx, ty):
    return tuple(grid[ty * 8 + y][tx * 8 + x] for y in range(8) for x in range(8))


def oriented(pixels):
    """Yield (h, v, pixels drawn with that flip) in fixed order: none, H, V, HV."""
    rows = [pixels[y * 8:(y + 1) * 8] for y in range(8)]
    for h, v in ((False, False), (True, False), (False, True), (True, True)):
        out = [r[::-1] if h else r for r in (rows[::-1] if v else rows)]
        yield h, v, tuple(c for r in out for c in r)


def label_types(tile, classes):
    if ('class' in tile) == ('types' in tile):
        raise ValueError(f'tile {tile["id"]} needs exactly one of class or types')
    if 'class' in tile:
        if tile['class'] not in classes:
            raise ValueError(f'tile {tile["id"]} names unknown class {tile["class"]!r}')
        return tile['class'], set(classes[tile['class']])
    ids = tile['types']
    if not isinstance(ids, list) or not ids or any(not integer(v) or not 0 <= v <= 255 for v in ids) or len(set(ids)) != len(ids):
        raise ValueError(f'tile {tile["id"]} types must be unique integers 0-255')
    return 'types:' + ','.join(str(v) for v in sorted(ids)), set(ids)


def check_spec(spec):
    if not isinstance(spec, dict) or spec.get('schema') != 1:
        raise ValueError('spec must be schema 1')
    unknown = sorted(set(spec) - SPEC_KEYS)
    if unknown:
        raise ValueError(f'unknown spec keys: {unknown}')
    if spec.get('world') not in ('overworld', 'dungeon'):
        raise ValueError('world must be overworld or dungeon')
    slots = spec.get('slots')
    if not isinstance(slots, list) or not slots or any(not integer(s) or not 0 <= s <= 7 for s in slots) or len(set(slots)) != len(slots):
        raise ValueError('slots must be unique integers 0-7')
    blocksets = spec.get('blocksets') or []
    if not isinstance(blocksets, list) or any(not integer(b) or b < 0 for b in blocksets) or len(set(blocksets)) != len(blocksets):
        raise ValueError('blocksets must be unique nonnegative integers')
    needs = spec['world'] == 'dungeon' and any(s in (5, 6) for s in slots)
    if needs and not blocksets:
        raise ValueError('dungeon slot 5/6 requires blocksets')
    if blocksets and not needs:
        raise ValueError('blocksets apply only to dungeon slots 5/6')
    free = spec.get('free')
    if free is not None and (not isinstance(free, list) or any(not integer(i) or not 0 <= i <= 63 for i in free) or len(set(free)) != len(free)):
        raise ValueError('free must be unique indices 0-63 or null')
    if type(spec.get('dedupe_flips', True)) is not bool:
        raise ValueError('dedupe_flips must be true or false')
    tiles = spec.get('tiles')
    if not isinstance(tiles, list):
        raise ValueError('tiles must be an array')
    ids = set()
    for tile in tiles:
        if not isinstance(tile, dict) or not isinstance(tile.get('id'), str) or not tile['id']:
            raise ValueError('tiles require nonempty string ids')
        if tile['id'] in ids:
            raise ValueError(f'duplicate tile id {tile["id"]}')
        ids.add(tile['id'])
        unknown = sorted(set(tile) - TILE_KEYS)
        if unknown:
            raise ValueError(f'tile {tile["id"]} has unknown keys: {unknown}')
        cell = tile.get('cell')
        if not isinstance(cell, list) or len(cell) != 2 or any(not integer(v) or v < 0 for v in cell):
            raise ValueError(f'tile {tile["id"]} cell must be [column,row] in 8x8 units')
        if 'index' in tile and (not integer(tile['index']) or not 0 <= tile['index'] <= 63):
            raise ValueError(f'tile {tile["id"]} index must be 0-63')
    if tiles and not isinstance(spec.get('source'), str):
        raise ValueError('source is required when tiles are given')
    return slots, blocksets


def share_search(keys, cands, budget=SEARCH_BUDGET):
    """Exact fallback: give each pixel key a set of indices so every tile has a candidate owned by its key.

    Tiles with equal keys share an index; different keys never do. Returns ({index: key}, None) on
    success, or (None, 'complete'|'exhausted') when no placement exists or the node budget ran out.
    """
    owner, failed, nodes = {}, set(), [0]

    def hall(open_tiles):
        # Each key with an unsatisfied tile needs its own new index: a key matching must cover them all.
        need = {}
        for t in open_tiles:
            need.setdefault(keys[t], set()).update(i for i in cands[t] if i not in owner)
        match = {}

        def augment(key, seen):
            for i in sorted(need[key]):
                if i not in seen:
                    seen.add(i)
                    if i not in match or augment(match[i], seen):
                        match[i] = key
                        return True
            return False

        return all(augment(key, set()) for key in need)

    def solve():
        state = frozenset(owner.items())
        if state in failed:
            return False
        nodes[0] += 1
        if nodes[0] > budget:
            raise OverflowError
        open_tiles = [t for t in range(len(keys)) if not any(owner.get(i) == keys[t] for i in cands[t])]
        if not open_tiles:
            return True
        best = None
        for t in open_tiles:
            opts = [i for i in cands[t] if i not in owner]
            if not opts:
                failed.add(state)
                return False
            if best is None or len(opts) < len(best[1]):
                best = (t, opts)
        if hall(open_tiles):
            t, opts = best
            for i in opts:
                owner[i] = keys[t]
                if solve():
                    return True
                del owner[i]
        failed.add(state)
        return False

    try:
        return (dict(owner), None) if solve() else (None, 'complete')
    except OverflowError:
        return None, 'exhausted'


def regroup(entries, owner):
    """Groups for a share_search result: each tile takes its lowest owned candidate; unused indices stay free."""
    groups = {}
    for e in entries:
        index = min(i for i in e['candidates'] if owner.get(i) == e['key'])
        if index not in groups:
            groups[index] = {'index': index, 'pixels': e['pixels'], 'labels': [], 'members': []}
        group = groups[index]
        h, v = next((h, v) for h, v, view in oriented(e['pixels']) if view == group['pixels'])
        group['labels'].append(e['label'])
        group['members'].append({'id': e['tile']['id'], 'cell': e['tile']['cell'], 'h_flip': h, 'v_flip': v})
    return list(groups.values())


def place(spec, types, classes, source=None, base=None):
    """Return a JSON-safe result; result['grid'] is the 32x128 sheet when every tile is placed.

    source: rows of indices (or None); base: 32x128 rows (or None). Raises ValueError on bad input.
    """
    slots, blocksets = check_spec(spec)
    ctx = contexts(types, spec['world'], slots, blocksets)
    if base is not None:
        base_tiles = [tile_at(base, i % 16, i // 16) for i in range(64)]
        default_free = [i for i in range(64) if not any(base_tiles[i])]
    else:
        default_free = list(range(64))
    free = sorted(spec['free']) if spec.get('free') is not None else default_free
    tiles = spec['tiles']
    if tiles and source is None:
        raise ValueError('source is required when tiles are given')
    labels = {}
    groups = []
    entries = []
    for tile in tiles:
        label, tset = label_types(tile, classes)
        labels.setdefault(label, tset)
        cx, cy = tile['cell']
        if (cx + 1) * 8 > len(source[0]) or (cy + 1) * 8 > len(source):
            raise ValueError(f'tile {tile["id"]} cell {tile["cell"]} is outside the source')
        pixels = tile_at(source, cx, cy)
        cands = [i for i in free if all(t[i] in tset for _, _, t in ctx)]
        pin = tile.get('index')
        if pin is not None and pin not in cands:
            raise ValueError(f'tile {tile["id"]} pin {pin} is not a candidate (free indices of its type: {cands})')
        if pin is not None:
            cands = [pin]
        views = list(oriented(pixels)) if spec.get('dedupe_flips', True) else [(False, False, pixels)]
        entries.append({'tile': tile, 'label': label, 'pixels': pixels, 'key': min(v for _, _, v in views), 'candidates': cands})
        member = None
        for group in groups:
            shared = [i for i in group['candidates'] if i in cands]
            if not shared:
                continue
            for h, v, view in oriented(pixels):
                if (h or v) and not spec.get('dedupe_flips', True):
                    break
                if view == group['pixels']:
                    member = (group, h, v, shared)
                    break
            if member:
                break
        if member:
            group, h, v, shared = member
            group['candidates'] = shared
            group['types'] &= tset
            group['pin'] = group['pin'] if pin is None else pin
            group['labels'].append(label)
            group['members'].append({'id': tile['id'], 'cell': tile['cell'], 'h_flip': h, 'v_flip': v})
        else:
            groups.append({'pixels': pixels, 'candidates': cands, 'types': set(tset), 'pin': pin,
                           'labels': [label], 'members': [{'id': tile['id'], 'cell': tile['cell'], 'h_flip': False, 'v_flip': False}]})
    pinned = {}
    for group in groups:
        if group['pin'] is not None:
            if group['pin'] in pinned:
                raise ValueError(f'tiles {pinned[group["pin"]]} and {group["members"][0]["id"]} pin index {group["pin"]} with different pixels')
            pinned[group['pin']] = group['members'][0]['id']
    order = [g for g in groups if g['pin'] is not None] + [g for g in groups if g['pin'] is None]
    match = {}

    def augment(n, seen):
        # Kuhn augmenting path; an unused candidate is taken before any earlier tile is displaced,
        # so tiles keep spec order on ascending indices when nothing forces a move.
        cands = order[n]['candidates']
        for i in cands:
            if i not in match and i not in seen:
                seen.add(i)
                match[i] = n
                return True
        for i in cands:
            if i not in seen and i in match:
                seen.add(i)
                if augment(match[i], seen):
                    match[i] = n
                    return True
        return False

    for n in range(len(order)):
        augment(n, set())
    where = {n: i for i, n in match.items()}
    demand = {label: sum(1 for g in groups if label in g['labels']) for label in labels}
    capacity = []
    for label, tset in (labels.items() if tiles else ((k, set(v)) for k, v in classes.items())):
        per = [{'slot': s, 'blockset': b, 'indices': [i for i in range(64) if t[i] in tset],
                'free': [i for i in free if t[i] in tset]} for s, b, t in ctx]
        capacity.append({'class': label, 'types': sorted(tset), 'demand': demand.get(label, 0),
                         'candidates': [i for i in free if all(t[i] in tset for _, _, t in ctx)], 'slots': per})
    result = {'world': spec['world'], 'slots': slots, 'blocksets': blocksets, 'free': free,
              'dedupe_flips': spec.get('dedupe_flips', True), 'tile_count': len(tiles), 'unique_tiles': len(groups),
              'capacity': capacity, 'types_by_index': [{'slot': s, 'blockset': b, 'types': t} for s, b, t in ctx]}
    unplaced = [g for n, g in enumerate(order) if n not in where]
    if unplaced:
        # Greedy grouping can join tiles whose shared index blocks another tile; search per tile instead.
        owner, search = share_search([e['key'] for e in entries], [e['candidates'] for e in entries])
        if owner is not None:
            order = regroup(entries, owner)
            where = {n: g['index'] for n, g in enumerate(order)}
            unplaced = []
            result['unique_tiles'] = len(order)
            demand = {label: sum(1 for g in order if label in g['labels']) for label in labels}
            for entry in result['capacity']:
                entry['demand'] = demand.get(entry['class'], 0)
    if unplaced:
        result['status'] = 'unplaced'
        result['search'] = search
        result['unplaced'] = [{'ids': [m['id'] for m in g['members']], 'classes': sorted(set(g['labels'])),
                               'candidates': g['candidates']} for g in unplaced]
        return result
    grid = [list(row) for row in base] if base is not None else [[0] * 128 for _ in range(32)]
    placed = []
    for n, group in enumerate(order):
        index = where[n]
        tx, ty = (index % 16) * 8, (index // 16) * 8
        for k, value in enumerate(group['pixels']):
            grid[ty + k // 8][tx + k % 8] = value
        for m in group['members']:
            placed.append({**m, 'index': index, 'chars': [s * 0x40 + index for s in slots],
                           'types': [{'slot': s, 'blockset': b, 'type': t[index]} for s, b, t in ctx]})
    spec_order = {t['id']: n for n, t in enumerate(tiles)}
    placed.sort(key=lambda p: spec_order[p['id']])
    result['status'] = 'placed' if tiles else 'audit'
    result['placed_indices'] = sorted(where.values())
    result['tiles'] = placed
    result['grid'] = grid
    return result


def class_color(tile_type, classes):
    for name, ids in classes.items():
        if tile_type in ids:
            return COLORS.get(name, OTHER)
    return OTHER


def preview(grid, palette, ctx_types, classes, placed):
    """One 4x panel per slot x blockset; frame = type-class colour, white corner square = placed."""
    pal = palette or [c for i in range(8) for c in (i * 36, i * 36, i * 36)]
    sheet = Image.new('P', (128, 32))
    sheet.putpalette(pal)
    sheet.putdata([v for row in grid for v in row])
    big = sheet.convert('RGB').resize((128 * SCALE, 32 * SCALE), Image.NEAREST)
    gap = 8
    image = Image.new('RGB', (big.width, len(ctx_types) * (big.height + gap) - gap), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    cell = 8 * SCALE
    for n, entry in enumerate(ctx_types):
        y0 = n * (big.height + gap)
        image.paste(big, (0, y0))
        for i, tile_type in enumerate(entry['types']):
            x, y = (i % 16) * cell, y0 + (i // 16) * cell
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], outline=class_color(tile_type, classes), width=2)
            if i in placed:
                draw.rectangle([x + 3, y + 3, x + 9, y + 9], fill=(255, 255, 255), outline=(0, 0, 0))
    return image


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--types', type=Path, required=True, help='slot_types.json (schema 1)')
    parser.add_argument('--classes', type=Path, default=DEFAULT_CLASSES)
    parser.add_argument('--out', type=Path, required=True, help='new output directory')
    args = parser.parse_args()
    try:
        if args.out.exists():
            raise ValueError('--out already exists; inputs and previous outputs are never replaced')
        codec = sheet_codec()
        spec = json.loads(args.spec.read_text())
        types = load_types(args.types)
        classes = load_classes(args.classes)
        inputs = {'spec': args.spec, 'types': args.types, 'classes': args.classes}
        source = palette = base = None
        if isinstance(spec, dict) and isinstance(spec.get('source'), str):
            inputs['source'] = args.spec.parent / spec['source']
            source, palette = read_source(inputs['source'])
        if isinstance(spec, dict) and spec.get('base_sheet') is not None:
            if not isinstance(spec['base_sheet'], str):
                raise ValueError('base_sheet must be a path or null')
            inputs['base_sheet'] = args.spec.parent / spec['base_sheet']
            base, base_palette = read_base(inputs['base_sheet'], codec)
            palette = palette or base_palette
        result = place(spec, types, classes, source, base)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f'place_tiles: error: {error}', file=sys.stderr)
        sys.exit(1)
    grid = result.pop('grid', None)
    tiles = result.pop('tiles', [])
    report = {'schema': 1, 'inputs': {k: {'path': str(p.resolve()), 'sha256': sha256(p)} for k, p in inputs.items()}, **result}
    args.out.mkdir()
    if result['status'] == 'unplaced':
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'place_tiles: {len(result["unplaced"])} unique tile(s) unplaced; see {args.out / "report.json"}', file=sys.stderr)
        sys.exit(2)
    preview(grid, palette, result['types_by_index'], classes, set(result['placed_indices'])).save(args.out / 'preview.png')
    if result['status'] == 'placed':
        sheet = Image.new('P', (codec.W, codec.H), 0)
        sheet.putpalette(palette)
        sheet.putdata([v for row in grid for v in row])
        sheet.save(args.out / 'sheet.png', transparency=0)
        binary = codec.grid_to_sheet(grid)
        (args.out / 'sheet.bin').write_bytes(binary)
        report['outputs'] = {'sheet_png_sha256': sha256(args.out / 'sheet.png'), 'sheet_bin_sha256': hashlib.sha256(binary).hexdigest()}
        placement = {'schema': 1, 'world': result['world'], 'slots': result['slots'], 'blocksets': result['blocksets'], 'tiles': tiles}
        (args.out / 'placement.json').write_text(json.dumps(placement, indent=2) + '\n')
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output': str(args.out.resolve()), 'status': result['status'], 'tiles': result['tile_count'], 'unique_tiles': result['unique_tiles']}))


if __name__ == '__main__':
    main()
