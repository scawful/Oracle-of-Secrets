#!/usr/bin/env python3
"""Emit bounded D4 water/service/gate collision runs; never write a ROM.

Format: dw offset, db positive count, value; FFFF end. Offsets address
COLMAPA then COLMAPB, and no existing interroom stair/door/key cell is changed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct

import sky_d8_room_writer as rooms


def decode(rec):
    if rec[0] >= 0xfc or rec[2] >= 0xf8:
        a, x, y = rooms.decode_object(rec)
        return a, x, y, 0
    return rec[2], rec[0] >> 2, rec[1] >> 2, ((rec[0] & 3) << 2) | (rec[1] & 3)


def rectangle(changes, x, y, width, height, value, layers=(0, 1)):
    for layer in layers:
        for yy in range(y, y + height):
            for xx in range(x, x + width):
                assert 0 <= xx < 64 and 0 <= yy < 64
                changes[layer * 4096 + yy * 64 + xx] = value


def tables(root):
    data = (root / 'Data/Rooms/d4_water/25-high.bin').read_bytes()
    high = rooms.parse_object_stream(data, 0, len(data))
    water = set()
    for rec in high.lists[1]:
        a, x, y, n = decode(rec)
        if a in (0xc9, 0xe7):
            water.update(yy * 64 + xx for yy in range(y, y + 4 * ((n & 3) + 1))
                         for xx in range(x, x + 4 * ((n >> 2) + 1)))
    result = {}
    for state in ('low', 'high'):
        changes = {4096 + cell: 8 if state == 'high' else 0 for cell in water}
        rectangle(changes, 38, 47, 8, 5, 0)
        rectangle(changes, 36, 47, 2, 6, 1)
        rectangle(changes, 46, 47, 2, 6, 1)
        rectangle(changes, 36, 52, 12, 3, 1)
        if state == 'low':
            rectangle(changes, 36, 48, 4, 4, 0)
            rectangle(changes, 41, 49, 2, 2, 0x3b, (0,))
            rectangle(changes, 22, 44, 4, 1, 0, (0,))
            # The original133 art also contributes two08 cells one row below
            # its generated water strip. Clear those only while drained;
            # retain the02 side posts and all stair/layer-switch records.
            rectangle(changes, 23, 45, 2, 1, 0, (0,))
            for x in (22, 30, 51):
                rectangle(changes, x, 44, 4, 1, 2, (1,))
            sentinel = 44 * 64 + 22  # native133 forces08; drained approach needs00
        else:
            rectangle(changes, 38, 47, 8, 5, 1)  # sealed maintenance cover
            # Intended vanilla135 water-hop flags at the unchanged two anchors.
            # The old mixed133/135 list order overwrites the native hop count.
            for x in (30, 51):
                for dx, value in enumerate((3, 0, 0, 3)):
                    changes[43 * 64 + x + dx] = value
                for dx, value in enumerate((3, 10, 10, 3)):
                    changes[4096 + 43 * 64 + x + dx] = value
            # The selected High stream already gives E7 water its target08.
            # Use the maintenance star beneath the sealed cover instead:
            # native3B must become solid01, so the first High tick cannot skip.
            sentinel = 49 * 64 + 41
        result['25-' + state] = changes, sentinel
    closed = {}
    rectangle(closed, 22, 32, 24, 3, 1)
    result['37-closed'] = closed, 33 * 64 + 30  # original underwater floor00
    return result


def encode(changes, sentinel):
    # Put the sentinel first, once. It is a fast-path control, not an acceptance
    # test: the native caller independently compares every encoded cell.
    runs = [[sentinel, 1, changes[sentinel]]]
    for offset, value in sorted(changes.items()):
        if offset == sentinel:
            continue
        if len(runs) > 1 and offset == runs[-1][0] + runs[-1][1] and value == runs[-1][2] and runs[-1][1] < 255:
            runs[-1][1] += 1
        else:
            runs.append([offset, 1, value])
    assert len(changes) == sum(run[1] for run in runs)
    assert all(0 <= off < off + count <= 8192 for off, count, _ in runs)
    return b''.join(struct.pack('<HBB', *run) for run in runs) + b'\xff\xff', runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    audit = []
    for name, (changes, sentinel) in tables(root).items():
        raw, runs = encode(changes, sentinel)
        (args.output / (name + '-collision.bin')).write_bytes(raw)
        audit.append(dict(name=name, cells=len(changes), runs=len(runs), bytes=len(raw),
                          sentinel=[sentinel, changes[sentinel]],
                          sha256=hashlib.sha256(raw).hexdigest()))
    args.receipt.write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
