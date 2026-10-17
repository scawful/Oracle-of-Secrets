#!/usr/bin/env python3
"""ALTTP LC-LZ2 codec for graphics sheets (stdlib only).

decompress(): model of vanilla Decompress ($00:E79E): commands 0 direct,
1 byte fill, 2 word fill, 3 increment, 4 copy from absolute output offset
(little-endian), $E0-$FE extended header (10-bit length), $FF end.
compress(): greedy encoder. stored(): direct-copy-only stream (no
compression; 1536 bytes -> 1541 bytes), trivially correct.
"""

def decompress(buf, start=0, max_output=0x4000):
    if not 0 <= start < len(buf):
        raise ValueError('compressed stream starts outside input')
    p = start; o = bytearray()
    def take(n):
        nonlocal p
        if p + n > len(buf):
            raise ValueError('truncated compressed stream')
        data = buf[p:p+n]; p += n
        return data
    while True:
        b = take(1)[0]
        if b == 0xFF: break
        cmd = b >> 5
        if cmd == 7:
            cmd = (b >> 2) & 7; ln = (((b & 3) << 8) | take(1)[0]) + 1
        else:
            ln = (b & 0x1F) + 1
        if len(o) + ln > max_output:
            raise ValueError('decompressed stream exceeds limit')
        if cmd == 0: o += take(ln)
        elif cmd == 1: o += bytes(take(1)) * ln
        elif cmd == 2:
            a, c = take(2)
            for k in range(ln): o.append(a if k % 2 == 0 else c)
        elif cmd == 3:
            a = take(1)[0]
            for k in range(ln): o.append((a + k) & 0xFF)
        elif cmd == 4:
            off = int.from_bytes(take(2), 'little')
            if off >= len(o):
                raise ValueError('copy references unavailable output')
            for k in range(ln): o.append(o[off + k])
        else:
            raise ValueError(f'bad command {cmd} at {p-1}')
    return bytes(o), p - start

def _hdr(cmd, ln):
    assert 1 <= ln <= 1024 and 0 <= cmd <= 4
    if ln <= 32:
        return bytes([(cmd << 5) | (ln - 1)])
    return bytes([0xE0 | (cmd << 2) | ((ln - 1) >> 8), (ln - 1) & 0xFF])

def _emit_direct(out, lit):
    i = 0
    while i < len(lit):
        n = min(1024, len(lit) - i)
        out += _hdr(0, n) + lit[i:i+n]; i += n

def stored(data):
    out = bytearray(); _emit_direct(out, bytes(data)); out.append(0xFF)
    return bytes(out)

def compress(data):
    data = bytes(data); n = len(data); out = bytearray(); lit = bytearray(); i = 0
    while i < n:
        best = (0, None, None)  # (saving, cmd, (ln, payload))
        # 1 byte fill
        ln = 1
        while i + ln < n and ln < 1024 and data[i+ln] == data[i]: ln += 1
        cands = [(1, ln, bytes([data[i]]))]
        # 2 word fill
        if i + 1 < n:
            ln = 2
            while i + ln < n and ln < 1024 and data[i+ln] == data[i + (ln & 1)]: ln += 1
            cands.append((2, ln, data[i:i+2]))
        # 3 increment
        ln = 1
        while i + ln < n and ln < 1024 and data[i+ln] == (data[i] + ln) & 0xFF: ln += 1
        cands.append((3, ln, bytes([data[i]])))
        # 4 copy (absolute offset, may overlap)
        bl, bo = 0, 0
        for j in range(0, i):
            ln = 0
            while i + ln < n and ln < 1024 and data[j+ln] == data[i+ln]: ln += 1
            if ln > bl: bl, bo = ln, j
        if bl: cands.append((4, bl, bytes([bo & 0xFF, bo >> 8])))
        for cmd, ln, pay in cands:
            cost = len(_hdr(cmd, ln)) + len(pay)
            saving = ln - cost
            if saving > best[0]: best = (saving, cmd, (ln, pay))
        if best[1] is None:
            lit.append(data[i]); i += 1; continue
        _emit_direct(out, bytes(lit)); lit = bytearray()
        cmd, (ln, pay) = best[1], best[2]
        out += _hdr(cmd, ln) + pay; i += ln
    _emit_direct(out, bytes(lit)); out.append(0xFF)
    res = bytes(out)
    assert decompress(res)[0] == data, 'round-trip failed'
    return res

if __name__ == '__main__':
    import os
    for t in (b'', bytes(1536), os.urandom(1536), bytes(range(256)) * 6):
        for enc in (stored, compress):
            e = enc(t); assert decompress(e)[0] == t, enc.__name__
    print('self-test ok')
