#!/usr/bin/env python3
"""Bind the native dock library and write a pinned, private four-screen recipe.

Only new Map16/Map32 definitions, 30/31/32/33 map pointers, bank44C000 streams
and ROM size/checksum metadata change. All other maps, collision, entrances,
wide-map transitions and Dragon Ship data must remain byte-identical.

Map decoding follows Yaze HyruleMagicDecompress(big_endian=1), and the
expanded quadrant packing in Overworld::GetTile16ForTile32. New streams use
literal-only LC-LZ2, avoiding ambiguity in copy-offset byte order.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from kalyxo_docks_art import decode_4bpp, encode_4bpp
from lz2 import stored

ROOT = Path(__file__).resolve().parents[2]
BASE_SHA = "e75690add9200a8db00a44772b5aaf05c04284616ec8aaf9aa02919096ed14ac"
QUADRANTS = (0x18000, 0x20000, 0x1F0000, 0x1F8000)
COUNT32 = 0x67E0 // 6 * 4
MAPS = (0x30, 0x31, 0x32, 0x33)
PROFILE_MAPS = (0x30, 0x31, 0x32)
FIRST16 = 0xFC0  # Keep R08/R09's private lava definitions $F80-$F88 distinct.
STREAM_PC = 0x224000  # SNES $44C000, after profile assets/helpers.


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pc(address):
    if not address & 0x8000:
        raise ValueError(f"not a LoROM address: {address:06X}")
    return ((address & 0x7F0000) >> 1) | (address & 0x7FFF)


def snes(address):
    return (address // 0x8000 << 16) | 0x8000 | (address & 0x7FFF)


def decode_map(data, start):
    out = bytearray()
    p = start
    while True:
        h = data[p]
        p += 1
        if h == 255:
            break
        cmd, n = h >> 5, (h & 31) + 1
        if cmd == 7:
            cmd, n = (h >> 2) & 7, ((h & 3) << 8 | data[p]) + 1
            p += 1
        if len(out) + n > 256:
            raise ValueError("map stream exceeds 256 cells")
        if cmd == 0:
            out.extend(data[p:p + n]); p += n
        elif cmd == 1:
            out.extend([data[p]] * n); p += 1
        elif cmd == 2:
            a, b = data[p:p + 2]; p += 2
            out.extend(a if i % 2 == 0 else b for i in range(n))
        elif cmd == 3:
            a = data[p]; p += 1
            out.extend((a + i) & 255 for i in range(n))
        elif cmd in (4, 5, 6):
            offset = data[p] << 8 | data[p + 1]; p += 2
            for i in range(n):
                out.append(out[offset + i])
        else:
            raise ValueError("invalid map compression command")
    if len(out) != 256:
        raise ValueError("map stream is not 256 cells")
    return out


def definitions32(data):
    result = []
    for index in range(COUNT32):
        group, q = index // 4 * 6, index % 4
        values = []
        for base in QUADRANTS:
            p = base + group
            packed = data[p + (4 if q < 2 else 5)]
            values.append(data[p + q] | (((packed >> (4 if q % 2 == 0 else 0)) & 15) << 8))
        result.append(tuple(values))
    return result


def maps32(data):
    result = []
    for screen in range(160):
        streams = [decode_map(data, pc(int.from_bytes(data[t + screen * 3:t + screen * 3 + 3], "little")))
                   for t in (0x1794D, 0x17B2D)]
        result.append([h << 8 | l for h, l in zip(*streams)])
    return result


def expand(ids, defs):
    rows = [[0] * 32 for _ in range(32)]
    for index, tile in enumerate(ids):
        x, y = index % 16 * 2, index // 16 * 2
        a, b, c, d = defs[tile]
        rows[y][x:x + 2] = [a, b]
        rows[y + 1][x:x + 2] = [c, d]
    return rows


def write_definition(data, index, values, allowed):
    group, q = index // 4 * 6, index % 4
    for base, tile in zip(QUADRANTS, values):
        p = base + group
        data[p + q] = tile & 255
        high = p + (4 if q < 2 else 5)
        shift = 4 if q % 2 == 0 else 0
        data[high] = (data[high] & ~(15 << shift)) | ((tile >> 8) << shift)
        allowed.update((p + q, high))


def compile_native(base, layout):
    if len(base) != 0x200000 or sha(base) != BASE_SHA:
        raise ValueError("base identity mismatch; re-audit allocations before rebasing")
    defs = definitions32(base)
    maps = maps32(base)
    all16 = {v for d in defs for v in d}
    if set(range(FIRST16, FIRST16 + 64)) & all16:
        raise ValueError("reserved Map16 range is referenced")
    attrs = [struct.unpack_from("<4H", base, 0x1E8000 + i * 8) for i in range(4096)]
    used = {w & 1023 for m in (*PROFILE_MAPS, 0x9F) for t in maps[m] for v in defs[t] for w in attrs[v]}
    if used & set(range(0xC0, 0x100)):
        raise ValueError("slot3 is not unused by docks, beach and overlay")
    collision = base[0x71459:0x71659]
    slots = {kind: iter([i for i in range(0xC0, 0x100) if collision[i] == value])
             for kind, value in (("walk", 0), ("solid", 1))}
    grid30 = expand(maps[0x30], defs)
    water_attr = attrs[grid30[20][20]][0]
    if collision[(water_attr & 1023) & 511] != 8:
        raise ValueError("water donor is not deep water")
    manifest_path = ROOT / "Data/graphics/kalyxo_docks/generated/manifest.json"
    art = json.loads(manifest_path.read_text())
    unique = (manifest_path.parent / "unique.4bpp").read_bytes()
    boat = (ROOT / "Overworld/gfx/boat.bin").read_bytes()
    ids = [cell["id"] for cell in art["cells"]]
    if len(boat) != 8192 or len(unique) % 32 or len(set(ids)) != len(ids) or any(type(i) is not int or not 0 <= i < 64 for i in ids):
        raise ValueError("art manifest or payload exceeds reserved allocation")
    for cell in art["cells"]:
        if [q["quadrant"] for q in cell["subtiles"]] != ["tl", "tr", "bl", "br"] or any(not 0 <= q["unique_art_index"] < len(unique) // 32 for q in cell["subtiles"]):
            raise ValueError("invalid quadrant order or canonical art index")
    bg = bytearray(boat)
    allocation, tile_bindings = {}, {}
    # Asar's expanded source allocations require zero-filled unused space.
    out = bytearray(base) + bytearray(0x400000 - len(base))
    allowed = set()
    for cell in art["cells"]:
        if cell["collision_intent"] == "unbound":
            continue
        words = []
        for subtile in cell["subtiles"]:
            intent = subtile["collision_intent"]
            if intent == "water":
                words.append(water_attr)
                continue
            key = (subtile["unique_art_index"], intent)
            if key not in allocation:
                try:
                    slot = next(slots[intent])
                except StopIteration:
                    raise ValueError(f"not enough existing {intent} collision slots") from None
                pixels = decode_4bpp(unique[key[0] * 32:(key[0] + 1) * 32])
                pixels = [[v or 7 for v in row] for row in pixels]
                bg[(slot - 0xC0) * 32:(slot - 0xC0 + 1) * 32] = encode_4bpp(pixels)
                allocation[key] = slot
            word = allocation[key] | (3 << 10) | (int(subtile["hflip"]) << 14) | (int(subtile["vflip"]) << 15)
            words.append(word)
        tile_id = FIRST16 + cell["id"]
        offset = 0x1E8000 + tile_id * 8
        out[offset:offset + 8] = struct.pack("<4H", *words)
        allowed.update(range(offset, offset + 8))
        tile_bindings[cell["name"]] = dict(tile16=tile_id, words=words, collision_intent=cell["collision_intent"])

    if layout["schema_version"] != 1 or layout["grid_pixels"] != 16:
        raise ValueError("layout must be schema1 on the16-pixel grid")
    deck = set()
    for x0, y0, x1, y1 in layout["deck_rectangles"]:
        if not 0 <= x0 <= x1 < 96 or not 0 <= y0 <= y1 < 32:
            raise ValueError("deck rectangle outside three-screen grid")
        deck.update((x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
    rows = [sum((expand(maps[m], defs)[y] for m in MAPS), []) for y in range(32)]
    placements = {}
    for x, y in sorted(deck, key=lambda xy: (xy[1], xy[0])):
        north, south, west, east = ((x + dx, y + dy) not in deck for dx, dy in ((0,-1),(0,1),(-1,0),(1,0)))
        vertical = "north" if north else "south" if south else ""
        horizontal = "west" if west else "east" if east else ""
        name = "deck_" + vertical + horizontal if vertical or horizontal else ("planks_c" if (x + y * 3) % 17 == 0 else "planks_b" if (x + y) % 3 == 0 else "planks_a")
        placements[(x, y)] = name
    for item in layout["cargo"]:
        pos = (item["x"], item["y"])
        if pos not in deck:
            raise ValueError("cargo must stand on the deck")
        placements[pos] = item["tile"]
    for (x, y), name in placements.items():
        rows[y][x] = tile_bindings[name]["tile16"]
    # Add a one-cell solid fascia below exposed southern edges, without touching
    # the original beach terrain. Gaps between fingers remain native deep water.
    for x, y in sorted(deck):
        if x < 64 and y < 31 and (x, y + 1) not in deck:
            name = "fascia_pile" if x % 4 == 0 else "fascia"
            rows[y + 1][x] = tile_bindings[name]["tile16"]
            placements[(x, y + 1)] = name

    # Existing grass/tree donors keep Loom on its native graphics profile.
    native_placements = layout.get("native_placements", [])
    seen = set()
    for item in native_placements:
        screen, x, y, tile = (item[k] for k in ("screen", "x", "y", "tile16"))
        if any(type(v) is not int for v in (screen, x, y, tile)) or screen not in (0x32, 0x33) or not 0 <= x < 32 or not 0 <= y < 32 or not 0 <= tile < FIRST16:
            raise ValueError("native passage placement is outside its audited range")
        position = (screen, x, y)
        gx = (screen - 0x30) * 32 + x
        if position in seen or (gx, y) in placements:
            raise ValueError("duplicate or overlapping native passage placement")
        seen.add(position)
        if rows[y][gx] != item["old_tile16"]:
            raise ValueError("native passage source cell changed")
        if tile not in {v for row in expand(maps[screen], defs) for v in row}:
            raise ValueError("native passage donor is not used by its area")
        rows[y][gx] = tile

    used32 = {t for m in maps for t in m}
    free32 = iter(i for i in range(COUNT32) if i not in used32)
    lookup = {d:i for i,d in enumerate(defs) if i in used32}
    new32 = {}
    stream = STREAM_PC
    expected = {}
    for screen in MAPS:
        x0 = (screen - 0x30) * 32
        screen_rows = [r[x0:x0 + 32] for r in rows]
        expected[screen] = screen_rows
        ids = []
        for y in range(0, 32, 2):
            for x in range(0, 32, 2):
                key = (screen_rows[y][x], screen_rows[y][x + 1], screen_rows[y + 1][x], screen_rows[y + 1][x + 1])
                if key not in lookup:
                    index = next(free32)
                    lookup[key] = index
                    new32[index] = key
                    write_definition(out, index, key, allowed)
                ids.append(lookup[key])
        for table, shift in ((0x1794D, 8), (0x17B2D, 0)):
            packed = stored(bytes((v >> shift) & 255 for v in ids))
            if stream + len(packed) > 0x228000:
                raise ValueError("map streams exceed reserved upper bank44")
            out[stream:stream + len(packed)] = packed
            allowed.update(range(stream, stream + len(packed)))
            pointer = table + screen * 3
            out[pointer:pointer + 3] = snes(stream).to_bytes(3, "little")
            allowed.update(range(pointer, pointer + 3))
            stream += len(packed)
    out[0x7FD7] = 12
    allowed.add(0x7FD7)
    # Exact 4MiB image: checksum field contributes a constant 0x1FE.
    out[0x7FDC:0x7FE0] = b"\xff\xff\x00\x00"
    checksum = sum(out) & 0xFFFF
    out[0x7FDC:0x7FE0] = struct.pack("<HH", checksum ^ 0xFFFF, checksum)
    allowed.update(range(0x7FDC, 0x7FE0))
    padded = base + bytes(len(out) - len(base))
    differences = {i for i, (a,b) in enumerate(zip(padded, out)) if a != b}
    if differences - allowed:
        raise ValueError("writer escaped explicit byte allowlist")
    afterdefs, aftermaps = definitions32(out), maps32(out)
    for screen in range(160):
        actual = expand(aftermaps[screen], afterdefs)
        target = expected.get(screen, expand(maps[screen], defs))
        if actual != target:
            raise ValueError(f"map{screen:02X} roundtrip mismatch")
    if out[0x71459:0x71659] != collision:
        raise ValueError("collision table changed")
    binding = dict(schema_version=1, base_sha256=BASE_SHA, tile16_first=FIRST16,
                   palette_row=3, chr_slot=3, water_attr=water_attr,
                   tiles=tile_bindings,
                   chr=[dict(unique_art_index=k[0], collision_intent=k[1], chr=v, collision=collision[v]) for k,v in allocation.items()],
                   excluded={"ladder_bottom":"Reserved art only; climbing behavior is not implemented."})
    receipt = dict(base_sha256=BASE_SHA, output_sha256=sha(out), changed_existing_bytes=sum(i < len(base) for i in differences),
                   expanded_size=len(out), maps_changed=list(MAPS), map16_count=len(tile_bindings),
                   map32_allocated={f"{k:04X}":list(v) for k,v in new32.items()}, stream_pc_start=STREAM_PC, stream_pc_end=stream,
                   placements=[dict(x=x,y=y,tile=name,tile16=tile_bindings[name]["tile16"]) for (x,y),name in sorted(placements.items())],
                   native_placements=native_placements,
                   checks={"all_160_maps_roundtrip":True,"156_other_maps_identical":True,"collision_identical":True,"explicit_byte_allowlist":True},
                   assets={"kalyxo_docks_bg.bin":sha(bg),"kalyxo_docks_slot3.bin":sha(bg[:2048]),"boat.bin":sha(boat),"boat2.bin":sha((ROOT/"Overworld/gfx/boat2.bin").read_bytes())})
    return out, bytes(bg), binding, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--layout", type=Path, default=ROOT / "Data/overworld/kalyxo_docks.json")
    parser.add_argument("--write-assets", action="store_true", help="regenerate tracked profile binaries and binding")
    parser.add_argument("--dry-run", action="store_true", help="validate and emit a receipt without writing a ROM or assets")
    args = parser.parse_args()
    if args.out.resolve() == args.base.resolve() or args.out.exists():
        parser.error("output must be a new private path; never edit the input ROM")
    if args.receipt.resolve() in (args.base.resolve(), args.out.resolve()) or args.receipt.exists():
        parser.error("receipt must be a new path distinct from the input and output ROM")
    if args.dry_run and args.write_assets:
        parser.error("--dry-run cannot write tracked assets")
    out, bg, binding, receipt = compile_native(args.base.read_bytes(), json.loads(args.layout.read_text()))
    receipt["dry_run"] = args.dry_run
    if args.write_assets:
        (ROOT / "Overworld/gfx/kalyxo_docks_bg.bin").write_bytes(bg)
        (ROOT / "Overworld/gfx/kalyxo_docks_slot3.bin").write_bytes(bg[:2048])
        (ROOT / "Data/overworld/kalyxo_docks_binding.json").write_text(json.dumps(binding, indent=2) + "\n")
    if not args.dry_run:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("xb") as f:
            f.write(out)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x") as f:
        f.write(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k:v for k,v in receipt.items() if k not in ("placements","native_placements","map32_allocated")}, indent=2))


if __name__ == "__main__":
    main()
