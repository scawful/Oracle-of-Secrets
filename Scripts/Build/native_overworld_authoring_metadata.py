"""ID412 structural byte codec, matching Yaze's native authoring metadata.

The runtime actor stream remains authoritative for live code/coordinates.
This codec does not bind witnesses to that stream, assign rows or write a ROM.
"""
import struct

MAGIC = b'OWPLAC1\0'
SIZE = 8192
STRIDE = 32
PLACEMENT_SLOTS = 255


def require(value):
    if not value:
        raise ValueError('Invalid native overworld authoring metadata')


def decode(raw, materialized_count):
    require(type(raw) is bytes and len(raw) == SIZE
            and type(materialized_count) is int and materialized_count in (160, 192))
    magic, schema, stride, slots, occupied, next_id = struct.unpack_from('<8s4HI', raw)
    require(magic == MAGIC and (schema, stride, slots) == (1, STRIDE, PLACEMENT_SLOTS)
            and occupied <= PLACEMENT_SLOTS and next_id > 0
            and not any(raw[20:32]) and not any(raw[(occupied + 1) * STRIDE:]))
    rows, ids, bindings = [], set(), set()
    for index in range(occupied):
        p = raw[(index + 1) * STRIDE:(index + 2) * STRIDE]
        identity, kind, state, phase, presence = struct.unpack_from('<IBBBB', p)
        require(0 < identity < next_id and identity not in ids and state in (1, 2, 3))
        ids.add(identity)
        value = dict(id=identity, kind=kind, state=state)
        if kind == 1:
            owner, ordinal, y, x, code = p[8:13]
            require(state != 2 and phase < 3 and presence == 0
                    and owner < materialized_count and ordinal < 128 and y != 255
                    and not any(p[13:]))
            locator = phase, owner, ordinal
            if state == 1:
                require(locator not in bindings)
                bindings.add(locator)
            value.update(phase=phase, owner_map=owner, ordinal=ordinal, packed=[y, x, code])
        else:
            require(kind in (2, 3) and state != 1 and phase == 255 and presence <= 3
                    and p[8] < materialized_count and p[9] < 32 and p[10] < 32
                    and p[11] == 0 and not any(p[16:]))
            target, row = struct.unpack_from('<HH', p, 12)
            require((presence & 1 or target == 0) and (presence & 2 or row == 0))
            require((kind != 2 or target <= 255 and row <= 255)
                    and (kind != 3 or not presence & 2 or row < 0x4F))
            value.update(map=p[8], x=p[9], y=p[10],
                         target=target if presence & 1 else None,
                         row=row if presence & 2 else None)
        rows.append(value)
    return dict(next_placement_id=next_id, placements=rows)


def encode(metadata, materialized_count):
    require(type(metadata) is dict and set(metadata) == {'next_placement_id', 'placements'}
            and type(metadata['placements']) is list
            and len(metadata['placements']) <= PLACEMENT_SLOTS)

    def number(value, maximum):
        require(type(value) is int and 0 <= value <= maximum)
        return value

    raw = bytearray(SIZE)
    struct.pack_into('<8s4HI', raw, 0, MAGIC, 1, STRIDE, PLACEMENT_SLOTS,
                     len(metadata['placements']), number(metadata['next_placement_id'], 0xFFFFFFFF))
    for index, value in enumerate(metadata['placements']):
        require(type(value) is dict and value.get('kind') in (1, 2, 3))
        kind = number(value['kind'], 3)
        expected = {'id', 'kind', 'state'} | (
            {'phase', 'owner_map', 'ordinal', 'packed'} if kind == 1
            else {'map', 'x', 'y', 'target', 'row'})
        require(set(value) == expected)
        at = (index + 1) * STRIDE
        struct.pack_into('<IBB', raw, at, number(value['id'], 0xFFFFFFFF), kind,
                         number(value['state'], 255))
        if kind == 1:
            require(type(value['packed']) is list and len(value['packed']) == 3)
            raw[at + 6] = number(value['phase'], 255)
            raw[at + 8] = number(value['owner_map'], 255)
            raw[at + 9] = number(value['ordinal'], 255)
            raw[at + 10:at + 13] = bytes(number(v, 255) for v in value['packed'])
        else:
            raw[at + 6] = 255
            raw[at + 8:at + 11] = bytes(number(value[k], 255) for k in ('map', 'x', 'y'))
            for bit, key in enumerate(('target', 'row')):
                if value[key] is not None:
                    raw[at + 7] |= 1 << bit
                    struct.pack_into('<H', raw, at + 12 + bit * 2, number(value[key], 0xFFFF))
    encoded = bytes(raw)
    # One validator owns structural rules for both caller objects and ROM bytes.
    require(decode(encoded, materialized_count) == metadata)
    return encoded
