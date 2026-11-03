#!/usr/bin/env python3
"""Deterministic nearest-neighbor sprite normalization (Pillow; no ROM access)."""
import argparse
from collections import Counter
import hashlib
import json
import math
import re
from pathlib import Path
import struct
from PIL import Image


def data(image):
    # Pillow < 13 compatibility without the deprecated getdata path on 13+.
    return image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata()


def integer(value):
    return type(value) is int


def palette_colors(path, bpp):
    """Read little-endian BGR555 words or a JSON array of #RRGGBB strings.

    Hex entries take the same BGR555 round trip as hardware palette words.
    Never truncate a palette or mask a color index to fit the target depth.
    """
    path = Path(path)
    if path.suffix.lower() == '.bin':
        raw = path.read_bytes()
        if len(raw) % 2:
            raise ValueError('BGR555 palette must contain complete 16-bit words')
        words = list(struct.unpack('<' + 'H' * (len(raw) // 2), raw))
        if any(word > 0x7fff for word in words):
            raise ValueError('BGR555 palette word exceeds 15 bits')
    else:
        colors = json.loads(path.read_text())
        if not isinstance(colors, list):
            raise ValueError('hex palette must be a JSON array')
        words = []
        for color in colors:
            if not isinstance(color, str) or not re.fullmatch(r'#?[a-fA-F0-9]{6}', color):
                raise ValueError('hex palette entries must be RRGGBB strings')
            try:
                rgb = tuple(bytes.fromhex(color.lstrip('#')))
            except ValueError as error:
                raise ValueError('invalid hex palette entry') from error
            words.append(sum(round(c * 31 / 255) << (5 * n) for n, c in enumerate(rgb)))
    if not words or len(words) > 2 ** bpp:
        raise ValueError('palette entry count exceeds target bit depth or is empty')
    return [tuple(round(((word >> shift) & 31) * 255 / 31) for shift in (0, 5, 10)) for word in words]


def normalize(source, spec, colors):
    """Return a mode-P sheet and a JSON-safe, per-box conversion report."""
    bpp = spec.get('bpp')
    if type(bpp) is not int or bpp not in (3, 4):
        raise ValueError('bpp must be 3 or 4')
    if not colors or len(colors) > 2 ** bpp or any(len(c) != 3 or any(not integer(v) or v < 0 or v > 255 for v in c) for c in colors):
        raise ValueError('palette is invalid for target depth')
    if spec.get('transparent_index', 0) != 0:
        raise ValueError('transparent_index must be 0')
    size = spec.get('cell_size')
    if not isinstance(size, list) or len(size) != 2 or any(not integer(n) or n <= 0 for n in size):
        raise ValueError('cell_size must be positive integer [width,height]')
    boxes = spec.get('boxes')
    if not isinstance(boxes, list) or not boxes:
        raise ValueError('boxes must be a nonempty array')
    columns = spec.get('columns', len(boxes))
    if not integer(columns) or columns < 1 or columns > len(boxes):
        raise ValueError('columns must be within box count')
    threshold = spec.get('alpha_threshold', 192)
    limit = spec.get('close_match_error', 32)
    if not integer(threshold) or not 1 <= threshold <= 255:
        raise ValueError('alpha_threshold must be 1..255')
    if type(limit) not in (int, float) or not math.isfinite(limit) or limit < 0:
        raise ValueError('close_match_error must be finite and nonnegative')
    dimensions = (size[0] * columns, size[1] * math.ceil(len(boxes) / columns))
    if dimensions[0] * dimensions[1] > 1048576:
        raise ValueError('output exceeds 1048576 pixels')
    source = source.convert('RGBA')
    output = Image.new('P', dimensions, 0)
    output.putpalette([channel for color in colors for channel in color] + [0] * (768 - len(colors) * 3))
    output.info['transparency'] = 0
    report = {'bpp': bpp, 'transparent_index': 0, 'resample': 'NEAREST', 'dither': False, 'palette_rgb': colors, 'boxes': []}
    ids = set()
    for n, box in enumerate(boxes):
        if not isinstance(box, dict) or not isinstance(box.get('id'), str) or not box['id'] or box['id'] in ids:
            raise ValueError('boxes require unique string ids')
        ids.add(box['id'])
        rect = box.get('source_box')
        if not isinstance(rect, list) or len(rect) != 4 or any(not integer(v) for v in rect):
            raise ValueError('source_box must be [x,y,width,height]')
        x, y, w, h = rect
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > source.width or y + h > source.height:
            raise ValueError('source_box outside source image')
        allowed = box.get('allowed_indices')
        if not isinstance(allowed, list) or not allowed or any(not integer(v) or v <= 0 or v >= len(colors) or v >= 2 ** bpp for v in allowed) or len(set(allowed)) != len(allowed):
            raise ValueError('allowed_indices must name unique nontransparent in-depth palette entries')
        crop = source.crop((x, y, x + w, y + h))
        original_counts = Counter(data(crop))
        resized = crop.resize(tuple(size), Image.Resampling.NEAREST)
        counts = Counter(data(resized))
        mapping = {}
        color_report = []
        max_error = 0.0
        for rgba, count in sorted(counts.items()):
            if rgba[3] < threshold:
                index, error = 0, 0.0
            else:
                distance = lambda i: sum((rgba[k] - colors[i][k]) ** 2 for k in range(3))
                index = min(allowed, key=distance)
                error = math.sqrt(distance(index))
            mapping[rgba] = index
            max_error = max(max_error, error)
            color_report.append({'rgba': list(rgba), 'index': index, 'count': count, 'error': error, 'close_match': error <= limit})
        cell = Image.new('P', tuple(size), 0)
        cell.putdata([mapping[rgba] for rgba in data(resized)])
        output.paste(cell, (n % columns * size[0], n // columns * size[1]))
        report['boxes'].append({'id': box['id'], 'source_box': rect, 'allowed_indices': allowed, 'source_size': [w, h], 'target_size': size, 'size_changed': [w, h] != size, 'source_colors': [{'rgba': list(c), 'count': count} for c, count in sorted(original_counts.items())], 'mapping': color_report, 'max_color_error': max_error, 'no_close_match': [c for c in color_report if not c['close_match']], 'pixel_sha256': hashlib.sha256(cell.tobytes()).hexdigest()})
    report['pixel_sha256'] = hashlib.sha256(output.tobytes()).hexdigest()
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='new output directory')
    args = parser.parse_args()
    if args.out.exists():
        parser.error('--out already exists; inputs and previous outputs are never replaced')
    spec = json.loads(args.spec.read_text())
    if type(spec.get('bpp')) is not int or spec['bpp'] not in (3, 4):
        parser.error('bpp must be 3 or 4')
    colors = palette_colors(args.spec.parent / spec['palette'], spec['bpp'])
    with Image.open(args.source) as source:
        image, report = normalize(source, spec, colors)
    report['source_sha256'] = hashlib.sha256(args.source.read_bytes()).hexdigest()
    report['spec_sha256'] = hashlib.sha256(args.spec.read_bytes()).hexdigest()
    args.out.mkdir()
    image.save(args.out / 'indexed.png', transparency=0)
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output': str(args.out.resolve()), 'pixel_sha256': report['pixel_sha256']}))


if __name__ == '__main__':
    main()
