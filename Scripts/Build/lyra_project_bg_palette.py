"""Pure BG128 emission for compiled project maps; never selects storage or writes.

One bank contains 192 u16 byte offsets followed by deduplicated 256-byte BG
palettes. Offset zero means native behavior. Allocation/preimages come from the
owning producer; this source helper is not publication authorization.
"""
from __future__ import annotations

import hashlib
import struct

AREA_COUNT = 192
DIRECTORY_BYTES = AREA_COUNT * 2


def plan_bg128(maps, *, data_snes, capacity, preimage):
    """Plan explicitly owned data for MapPlan-like objects, including dependencies."""
    if (type(data_snes) is not int or not 0 <= data_snes <= 0xFFFFFF
            or data_snes & 0xFFFF < 0x8000
            or data_snes >> 16 in (0x7E, 0x7F)
            or type(capacity) is not int or capacity < DIRECTORY_BYTES
            or (data_snes & 0xFFFF) + capacity > 0x10000):
        raise ValueError('BG128 requires an explicit single mapped-bank allocation')
    if type(preimage) is not bytes or len(preimage) != capacity:
        raise ValueError('BG128 requires the complete allocation preimage')
    directory = [0] * AREA_COUNT
    palettes = bytearray()
    seen_maps, unique = set(), {}
    records = []
    for row in maps:
        area = row.map_id
        if type(area) is not int or not 0 <= area < AREA_COUNT or area in seen_maps:
            raise ValueError('BG128 invalid or duplicate compiled area')
        seen_maps.add(area)
        if 'background_palette' not in row.properties:
            continue
        words = row.properties['background_palette']
        if (not isinstance(words, (list, tuple)) or len(words) != 128
                or any(type(w) is not int or not 0 <= w <= 0x7FFF for w in words)):
            raise ValueError('BG128 requires exactly128 integer BGR555 words')
        raw = struct.pack('<128H', *words)
        if raw not in unique:
            unique[raw] = DIRECTORY_BYTES + len(palettes)
            palettes.extend(raw)
        directory[area] = unique[raw]
        records.append(dict(map_id=area, offset=directory[area],
                            sha256=hashlib.sha256(raw).hexdigest()))
    payload = struct.pack('<192H', *directory) + palettes
    if len(payload) > capacity:
        raise ValueError('BG128 payload exceeds explicit allocation')
    return dict(data_snes=data_snes, capacity=capacity, payload=payload,
                preimage_sha256=hashlib.sha256(preimage).hexdigest(),
                payload_sha256=hashlib.sha256(payload).hexdigest(), records=records,
                publication_authorized=False)


def emit_bg128_data(plan):
    """Return source data only; caller owns code/data placement and include order."""
    raw = plan['payload']
    lines = ['; Generated from compiled project BG128 properties; no OBJ data.',
             'pushpc', f"org ${plan['data_snes']:06X}", 'Oracle_ProjectBGPalette_Data:']
    for start in range(0, len(raw), 16):
        lines.append('db ' + ','.join(f'${v:02X}' for v in raw[start:start + 16]))
    lines += ['Oracle_ProjectBGPalette_DataEnd:',
              'assert Oracle_ProjectBGPalette_Data>>16 == (Oracle_ProjectBGPalette_DataEnd-1)>>16',
              f"assert pc() <= ${plan['data_snes'] + plan['capacity']:06X}", 'pullpc', '']
    return '\n'.join(lines)
