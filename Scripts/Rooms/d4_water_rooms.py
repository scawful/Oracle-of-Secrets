#!/usr/bin/env python3
"""Materialize the approved private D4 service-bay input, preserving other rooms.

The four native object streams are source assets reviewed as RAM-only renders.
Only room25 is changed in the editable input. Room37 stays original; the
controller selects its temporary closed-gate stream until the inlet releases.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import sky_d8_room_writer as rooms

SOURCE_SHA256 = 'e1478831c8e34208703296a77a15a63ce597b79cc731efcbfadcfee778448f36'
STREAM_HASHES = {
    '25-low': 'a500a0f2f9326f2eff05b3ca5fb0b938c801e00177dc02ffc19b3f66085836eb',
    '25-high': '50317fed0484137d7d80475a353cca3bd7d33a85a3b01daf2bb121080b54bf2f',
    '37-closed': 'da2fbd2b7d47a4011ea0dd099563be1140b937d4d1645fa04cd70ae971e1ca5b',
    '37-open': '46f02baebdfeb5af46edb13fae3e9e98ef78814e198c4ce61b1a8efa13f9fa15',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--write', action='store_true', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    source = args.source.resolve()
    base = source.read_bytes()
    assert sha(base) == SOURCE_SHA256, 'Unreviewed editable input'
    inv = rooms.build_inventory(base)
    streams = {}
    for name, expected in STREAM_HASHES.items():
        raw = (root / 'Data/Rooms/d4_water' / (name + '.bin')).read_bytes()
        assert sha(raw) == expected, name
        streams[name] = rooms.parse_object_stream(raw, 0, len(raw))
    assert streams['37-open'].header == inv.objects[0x37].header
    assert streams['37-open'].lists == inv.objects[0x37].lists
    assert streams['37-open'].doors == inv.objects[0x37].doors
    for name, stream in streams.items():
        old = inv.objects[int(name[:2], 16)]
        stairs = lambda lists: [rec for layer in lists for rec in layer
                               if rec[0] >= 0xfc and rooms.decode_object(rec)[0]
                               in (0x133, 0x135, 0x138, 0x139)]
        assert stairs(stream.lists) == stairs(old.lists), name
        assert stream.doors == old.doors, name
    stream = streams['25-low']
    raw, door_offset = rooms.encode_object_stream(stream.header, stream.lists, stream.doors)
    tail = max(item.end for item in inv.objects
               if rooms.OBJECT_ALLOC_REGION[0] <= item.pc < rooms.OBJECT_ALLOC_REGION[1])
    assert tail + len(raw) < rooms.OBJECT_ALLOC_REGION[1]
    assert not any(base[tail:tail + len(raw)])
    output = bytearray(base)
    edits = []

    def edit(pc, after, purpose):
        before = bytes(output[pc:pc + len(after)])
        assert len(before) == len(after)
        edits.append(dict(pc=pc, before=before.hex(), after=after.hex(), purpose=purpose))
        output[pc:pc + len(after)] = after

    edit(tail, raw, 'Approved room25 Low native objects')
    edit(rooms.OBJECT_TABLE_PC + 0x25 * 3, rooms.encode_long(tail, inv.obj_ptr[0x25]), 'Room25 object pointer')
    edit(rooms.DOOR_TABLE_PC + 0x25 * 3, rooms.encode_long(tail + door_offset, inv.door_ptr[0x25]), 'Same room25 door records')
    edit(inv.header_pc[0x25] + 4, b'\x00', 'Still water; remove inherited rapids/current')
    edit(inv.header_pc[0x25] + 5, b'\x00', 'Replace irreversible WaterOff tag with private controller')
    # The old one-way water-lever actor would compete with the new A control.
    start, end = inv.spr_span[0x25]
    assert list(inv.spr_span).count((start, end)) == 1
    assert base[start:end] == bytes.fromhex('00 06 07 21 05 13 39 ff')
    edit(start, bytes.fromhex('00 05 13 39 ff'), 'Replace obsolete native water-lever21; keep other actor39')
    final = bytes(output)
    ni = rooms.build_inventory(final)
    for room in range(296):
        before = rooms.logical_room(base, inv, room)
        after = rooms.logical_room(final, ni, room)
        if room != 0x25:
            assert before == after, room
        assert before['pots'] == after['pots'], room
        if room != 0x25:
            assert before['sprites'] == after['sprites'], room
    assert final[rooms.CHEST_TABLE_PC:rooms.CHEST_TABLE_PC + rooms.CHEST_CAPACITY] == base[rooms.CHEST_TABLE_PC:rooms.CHEST_TABLE_PC + rooms.CHEST_CAPACITY]
    assert final[0x128090:0x130000] == base[0x128090:0x130000]
    assert source.read_bytes() == base
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / 'd4-service-inlet-editable.sfc'
    assert not target.exists(), 'Use a fresh output directory'
    target.write_bytes(final)
    receipt = dict(source=str(source), sourceSha256=sha(base), output=str(target),
                   outputSha256=sha(final), edits=edits, streams=STREAM_HASHES,
                   other295RoomsExact=True, room37OriginalExact=True,
                   all296PotsAndChestDataExact=True, customCollisionInputExact=True,
                   obsoleteRoom25LeverReplaced=True, existingStairCoordinatesAndDestinationsExact=True)
    (args.output / 'LAYOUT_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(output=str(target), sha256=sha(final), changedBytes=sum(a != b for a, b in zip(base, final)))))


if __name__ == '__main__':
    main()
