#!/usr/bin/env python3
"""Inventory dungeon room shapes and generate pause-map data (bank $0A).

Commands:
  inventory  Render every registry room with z3ed, measure its 16x16 map
             footprint, and match it against the room-shape templates.
  generate   Build one dungeon's pause map (floor grids, shape per room,
             boss marker) and write a reviewed byte patch for
             Scripts/Build/apply_rom_byte_patch.py. Never writes a ROM.
  preview    Draw a dungeon's pause map from a ROM (or ROM + patch) to PNG.

Map format (usdasm bank_0A.asm, DungeonMap_*):
  - One map cell = one room = 16x16 px = 4 chars (NW, NE, SW, SE). One map
    pixel covers 4x4 room tiles, so a room's 16x16 occupancy grid is its map
    silhouette at native size.
  - Floors are 5x5 grids of room IDs ($0F = empty), stored lowest floor first.
    Each non-empty cell has one template byte, in grid order.
  - Boss floor is a signed byte from 1F (0 = 1F, -1 = B1); the game adds
    the basement count to get the grid index. The following byte's bit 7
    hides the boss icon and is independent of the floor.
  - Oracle uses ZScream's expanded template table at $21:9010 (256 slots).

Examples:
  python3 Scripts/Generate/dungeon_maps.py inventory --rom /tmp/copy.sfc --out /tmp/maps
  python3 Scripts/Generate/dungeon_maps.py generate --rom /tmp/copy.sfc --dungeon D1 \\
      --patch /tmp/maps/d1_patch.json --preview /tmp/maps/d1.png
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, deque
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "Docs/Dev/Planning/dungeons.json"
MAP_GFX = REPO / "Dungeons/dungeon_maps.bin"

FLOOR_COUNTS = 0x575D9      # 14 words: low nibble basements, high nibble floors 1F+
ROOM_PTRS = 0x57605         # 14 words: bank $0A pointer to 25-byte floor grids
TMPL_PTRS = 0x57BE4         # 14 words: bank $0A pointer to template bytes
BOSS_ROOMS = 0x56807        # 14 words, $000F = none
BOSS_FLOORS = 0x56E79       # 14 words, signed floor from 1F
DATA_START, DATA_END = 0x57039, 0x57CE0
# Tables inside the data region: floor counts + floor-grid pointers, shape-list pointers.
RESERVED = ((0x575D9, 0x57621), (TMPL_PTRS, TMPL_PTRS + 28))
TMPL_VANILLA, TMPL_EXPANDED, EXP_CHECK = 0x57009, 0x109010, 0x56652
EMPTY_WORD = 0x0B00
EMPTY = 0x0F

# Registry id -> pause-map dungeon slot ($040C / 2), from the bank $0F entrance table.
SLOTS = {"SOC": 0, "SOP": 3, "D2": 5, "D1": 6, "D6": 7, "D3": 8, "D5": 9,
         "SOW": 10, "D4": 11, "D7": 12, "FOS": 13}
QUADS = ("NW", "NE", "SW", "SE")
MATCH, CLOSE = 0.85, 0.70


def z3ed(*args: str) -> str:
    out = subprocess.run(["z3ed", *args], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"z3ed {' '.join(args)}: {out.stderr.strip()[:200]}")
    return out.stdout


def z3ed_json(*args: str) -> dict:
    text = z3ed(*args, "--format", "json")
    return json.loads(text[text.index("{"):])


def map_chars(path: Path = MAP_GFX) -> list[list[list[int]]]:
    """Map chars $300-$3FF as 8x8 color-index grids.

    Oracle DMAs Dungeons/dungeon_maps.bin over the vanilla map graphics
    (TransferDungeonMapGfx), so the in-game art is that file: 256 4bpp chars
    in the order of graphics sheets 212-215.
    """
    b = path.read_bytes()
    return [[[sum(((b[c * 32 + (p >> 1) * 16 + y * 2 + (p & 1)] >> (7 - x)) & 1) << p for p in range(4))
              for x in range(8)] for y in range(8)] for c in range(256)]


def word_pixels(chars, word: int) -> list[list[int]]:
    c = (word & 0x3FF) - 0x300
    tile = chars[c] if 0 <= c < 256 else [[0] * 8 for _ in range(8)]
    if word & 0x4000:
        tile = [row[::-1] for row in tile]
    if word & 0x8000:
        tile = tile[::-1]
    return tile


def template_pixels(chars, words) -> list[list[int]]:
    grid = [[0] * 16 for _ in range(16)]
    for q, word in enumerate(words):
        tile = word_pixels(chars, word)
        for y in range(8):
            for x in range(8):
                grid[(q >> 1) * 8 + y][(q & 1) * 8 + x] = tile[y][x]
    return grid


class MapRom:
    def __init__(self, data: bytes):
        self.data = bytearray(data)

    def word(self, pc: int) -> int:
        return self.data[pc] | self.data[pc + 1] << 8

    @staticmethod
    def pc(addr: int) -> int:
        return 0x50000 + (addr & 0x7FFF)  # bank $0A

    def template_base(self) -> int:
        return TMPL_VANILLA if self.data[EXP_CHECK] == 0xB9 else TMPL_EXPANDED

    def templates(self, count: int = 256) -> list[list[int]]:
        base = self.template_base()
        count = 186 if base == TMPL_VANILLA else count
        return [[self.word(base + i * 8 + k * 2) for k in range(4)] for i in range(count)]

    def dungeon(self, slot: int) -> dict:
        fc = self.data[FLOOR_COUNTS + slot * 2]
        basements, uppers = fc & 15, fc >> 4
        rp, tp = self.pc(self.word(ROOM_PTRS + slot * 2)), self.pc(self.word(TMPL_PTRS + slot * 2))
        floors, ti = [], 0
        for f in range(basements + uppers):
            grid = list(self.data[rp + f * 25: rp + f * 25 + 25])
            n = sum(1 for r in grid if r != EMPTY)
            floors.append({"name": floor_name(f, basements), "grid": grid,
                           "templates": list(self.data[tp + ti: tp + ti + n])})
            ti += n
        bf = self.data[BOSS_FLOORS + slot * 2]
        return {"basements": basements, "floors": floors,
                "boss_room": self.word(BOSS_ROOMS + slot * 2),
                "boss_floor": bf - 0x100 if bf & 0x80 else bf,
                "boss_icon_flags": self.data[BOSS_FLOORS + slot * 2 + 1]}


def floor_name(index: int, basements: int) -> str:
    return f"B{basements - index}" if index < basements else f"{index - basements + 1}F"


def floor_index(name: str, basements: int) -> int:
    return basements - int(name[1:]) if name.startswith("B") else basements + int(name[:-1]) - 1


# ---------------------------------------------------------------- footprints

PIT_DARK = 70  # pits render black or as a dark mesh; floor and wall tiles have brighter pixels
PIT_SHARE = 0.4  # a hand-drawn quadrant with more than this share of its pixels off the floor is redrawn


def occupancy(png: Path) -> list[list[int]]:
    """16x16 grid: 1 where the 4x4-tile block is floor, 0 where it is backdrop or pit."""
    from PIL import Image
    im = Image.open(png).convert("RGB")
    px = im.load()
    uniform, pit = {}, set()
    for ty in range(64):
        for tx in range(64):
            c = px[tx * 8, ty * 8]
            if all(px[tx * 8 + x, ty * 8 + y] == c for y in range(0, 8, 2) for x in range(0, 8, 2)):
                uniform[(tx, ty)] = c
            if all(max(px[tx * 8 + x, ty * 8 + y]) <= PIT_DARK for y in range(8) for x in range(8)):
                pit.add((tx, ty))
    ring = [c for (tx, ty), c in uniform.items() if tx in (0, 63) or ty in (0, 63)]
    if not ring:
        return [[1] * 16 for _ in range(16)]
    back = Counter(ring).most_common(1)[0][0]
    return [[0 if sum(uniform.get((tx, ty)) == back or (tx, ty) in pit
                      for ty in range(cy * 4, cy * 4 + 4) for tx in range(cx * 4, cx * 4 + 4)) >= 8 else 1
             for cx in range(16)] for cy in range(16)]


def quadrant_of(x: int, y: int) -> int:
    return (1 if x >= 32 else 0) | (2 if y >= 32 else 0)


def links(occ) -> set[tuple[int, int]]:
    """Quadrant pairs joined by drawn cells across their shared edge."""
    joined = set()
    for a, b, cells in ((0, 1, [((y, 7), (y, 8)) for y in range(8)]),
                        (2, 3, [((y, 7), (y, 8)) for y in range(8, 16)]),
                        (0, 2, [((7, x), (8, x)) for x in range(8)]),
                        (1, 3, [((7, x), (8, x)) for x in range(8, 16)])):
        if sum(occ[p][q] and occ[r][s] for (p, q), (r, s) in cells) >= 2:
            joined.add((a, b))
    return joined


def room_footprint(rom: Path, room: int, outdir: Path) -> dict:
    desc = z3ed_json("dungeon-describe-room", "--rom", str(rom), "--room", f"0x{room:02X}", "--include-objects")
    sprites = z3ed_json("dungeon-list-sprites", "--rom", str(rom), "--room", f"0x{room:02X}")
    png = outdir / f"room_{room:03X}.png"
    z3ed("dungeon-render", f"--rom={rom}", f"--room=0x{room:02X}", f"--output={png}", "--scale=1")
    occ = occupancy(png)
    content = set()
    for o in desc.get("objects", []):
        content.add(quadrant_of(o["x"], o["y"]))
    for d in desc.get("doors", []):
        content.add(quadrant_of(d["tile_x"], d["tile_y"]))
    for s in next(iter(sprites.values())).get("sprites", []):
        content.add(quadrant_of(s["x"] * 2, s["y"] * 2))
    filled = {q for q in range(4)
              if sum(occ[(q >> 1) * 8 + y][(q & 1) * 8 + x] for y in range(8) for x in range(8)) >= 8}
    joined = links(occ)
    used = set(content & filled) or set(filled)
    todo = deque(used)
    while todo:  # open quadrants joined to a used one are part of the room
        q = todo.popleft()
        for a, b in joined:
            for n in ((b,) if a == q else (a,) if b == q else ()):
                if n in filled and n not in used:
                    used.add(n)
                    todo.append(n)
    mask = [[occ[y][x] if quadrant_of(x * 4, y * 4) in used else 0 for x in range(16)] for y in range(16)]
    return {"layout": desc["properties"]["layout"], "used": sorted(used),
            "joined": sorted(f"{QUADS[a]}-{QUADS[b]}" for a, b in joined if a in used and b in used),
            "doors": [d["direction"][0] for d in desc.get("doors", [])],
            "footprint": ["".join(map(str, row)) for row in mask], "render": png.name}


def iou(a, b) -> float:
    inter = sum(1 for y in range(16) for x in range(16) if a[y][x] and b[y][x])
    union = sum(1 for y in range(16) for x in range(16) if a[y][x] or b[y][x])
    return inter / union if union else 1.0


def silhouettes(rom_data: bytes, gfx: Path = MAP_GFX) -> list[list[list[int]]]:
    chars = map_chars(gfx)
    return [[[1 if v else 0 for v in row] for row in template_pixels(chars, words)]
            for words in MapRom(rom_data).templates()]


def compose_template(fp, rom_data: bytes, gfx: Path = MAP_GFX) -> list[int]:
    """Build a new shape quadrant by quadrant from the char words hand-drawn
    templates already use (plus their flips), so the art and palettes stay the same."""
    chars = map_chars(gfx)
    used = Counter(w for words in MapRom(rom_data).templates() for w in words if any(words))
    pool = list(dict.fromkeys(w ^ flip for w, _ in used.most_common() for flip in (0, 0x4000, 0x8000, 0xC000)))
    words = []
    for q in range(4):
        want = [[fp[(q >> 1) * 8 + y][(q & 1) * 8 + x] for x in range(8)] for y in range(8)]
        words.append(max(pool, key=lambda w: sum((v != 0) == want[y][x]
                                                 for y, row in enumerate(word_pixels(chars, w))
                                                 for x, v in enumerate(row))))
    return words


def shape_key(fp: dict) -> str:
    return f"L{fp['layout']} {'+'.join(QUADS[q] for q in fp['used'])} [{' '.join(fp['joined'])}]"


def cmd_inventory(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    registry = json.loads(REGISTRY.read_text())["dungeons"]
    sil = silhouettes(args.rom.read_bytes(), args.gfx)
    in_use = [i for i, words in enumerate(MapRom(args.rom.read_bytes()).templates()) if any(words)]
    rows, clusters = [], []  # clusters: [footprint grid, [rooms]]
    for dng in registry:
        cur = MapRom(args.rom.read_bytes()).dungeon(SLOTS[dng["id"]]) if dng["id"] in SLOTS else None
        on_map = {}
        for f in (cur or {}).get("floors", []):
            for cell, r in enumerate(f["grid"]):
                if r != EMPTY:
                    on_map.setdefault(r, (f["name"], cell))
        for r in dng["rooms"]:
            room = int(r["id"], 16)
            if room > 0xFF:
                continue
            fp = room_footprint(args.rom, room, out)
            grid = [[int(c) for c in row] for row in fp["footprint"]]
            scores = sorted(((iou(grid, sil[i]), i) for i in in_use), reverse=True)
            best, tmpl = scores[0]
            for c in clusters:
                if iou(grid, c[0]) >= 0.9:
                    c[1].append(room)
                    shape = clusters.index(c)
                    break
            else:
                clusters.append([grid, [room]])
                shape = len(clusters) - 1
            floor, cell = on_map.get(room, (None, None))
            rows.append({"dungeon": dng["id"], "room": f"0x{room:02X}", "name": r.get("name", ""),
                         **fp, "shape": shape, "shape_key": shape_key(fp),
                         "map_floor": floor, "map_cell": cell,
                         "best_template": f"0x{tmpl:02X}", "iou": round(best, 3),
                         "match": "yes" if best >= MATCH else "close" if best >= CLOSE else "no"})
            print(f"{dng['id']:4} {room:02X} L{fp['layout']} {shape_key(fp):32} shape {shape:3} "
                  f"tmpl {tmpl:02X} iou {best:.2f}", file=sys.stderr)
    (out / "inventory.json").write_text(json.dumps(
        {"rom_sha1": hashlib.sha1(args.rom.read_bytes()).hexdigest(), "rooms": rows,
         "shapes": [{"shape": i, "rooms": [f"0x{r:02X}" for r in c[1]],
                     "footprint": ["".join(map(str, row)) for row in c[0]]} for i, c in enumerate(clusters)]},
        indent=1) + "\n")
    keys = Counter(r["shape_key"] for r in rows)
    print(f"{len(rows)} rooms, {len(clusters)} distinct footprints (IoU>=0.9), {len(keys)} layout+quadrant shapes; "
          f"existing shape match yes={sum(r['match'] == 'yes' for r in rows)} "
          f"close={sum(r['match'] == 'close' for r in rows)} no={sum(r['match'] == 'no' for r in rows)}")
    return 0


# ---------------------------------------------------------------- generator

STEP = {"N": (0, -1), "S": (0, 1), "W": (-1, 0), "E": (1, 0)}
OPPOSITE = {"N": "S", "S": "N", "W": "E", "E": "W"}


def referenced_templates(mr: MapRom) -> set[int]:
    """Shape slots any of the 14 dungeon maps uses, even all-zero ones."""
    return {t for s in range(14) for f in mr.dungeon(s)["floors"] for t in f["templates"]}


def parse_reach(items: list[str]) -> dict[int, set[int]]:
    reach = {}
    for item in items:
        room, _, quads = item.upper().partition("=")
        try:
            reach[int(room, 16)] = {QUADS.index(q) for q in quads.split("+")}
        except ValueError:
            raise SystemExit(f"--reach {item}: expected ROOM=QUADS, e.g. C8=SE or 40=NW+NE") from None
    return reach


def draft_spec(rom_data: bytes, dungeon_id: str, inventory: dict, render_dir: Path | None = None,
               reach: dict[int, set[int]] | None = None) -> dict:
    """Start from the current map, drop rooms outside the registry, then place
    unmapped registry rooms next to a mapped room they share a door with."""
    cur = MapRom(rom_data).dungeon(SLOTS[dungeon_id])
    rows = {int(r["room"], 16): r for r in inventory["rooms"] if r["dungeon"] == dungeon_id}
    floors = [{"name": f["name"], "grid": [EMPTY] * 25} for f in cur["floors"]]
    shapes, notes = {}, []
    for fi, f in enumerate(cur["floors"]):
        tmpl = iter(f["templates"])
        for cell, room in enumerate(f["grid"]):
            if room == EMPTY:
                continue
            t = next(tmpl)
            if room not in rows:
                notes.append(f"dropped {room:02X} from {f['name']}: not a {dungeon_id} room in the registry")
            elif room in shapes:
                notes.append(f"dropped second copy of {room:02X} on {f['name']}")
            else:
                floors[fi]["grid"][cell], shapes[room] = room, t
    placed = {room: (fi, cell) for fi, f in enumerate(floors) for cell, room in enumerate(f["grid"]) if room != EMPTY}
    progress = True
    while progress:
        progress = False
        for room in sorted(set(rows) - set(placed)):
            for d, (dx, dy) in STEP.items():
                n = room + dx + dy * 16
                if n not in placed or (n >> 4 != room >> 4 and dy == 0):
                    continue
                if d not in rows[room]["doors"] and OPPOSITE[d] not in rows[n]["doors"]:
                    continue
                fi, cell = placed[n]
                col, row = cell % 5 - dx, cell // 5 - dy
                if 0 <= col < 5 and 0 <= row < 5 and floors[fi]["grid"][row * 5 + col] == EMPTY:
                    floors[fi]["grid"][row * 5 + col] = room
                    placed[room] = (fi, row * 5 + col)
                    notes.append(f"placed {room:02X} on {floors[fi]['name']} beside {n:02X} (door {d})")
                    progress = True
                    break
    for room in sorted(set(rows) - set(placed)):
        notes.append(f"unplaced {room:02X}: no door to a mapped room; add it to the spec by hand")
    sil = silhouettes(rom_data)
    mr = MapRom(rom_data)
    referenced = referenced_templates(mr)
    free = [i for i, words in enumerate(mr.templates()) if not any(words) and i not in referenced]
    new_templates = {}
    for room in reach or {}:  # --reach applies exactly as asked, or the run stops
        png = render_dir / rows[room]["render"] if render_dir and room in rows else None
        why = ("not in this dungeon's inventory" if room not in rows else
               "not on the map" if room not in placed else
               "no room render" if not (png and png.exists()) else
               "needs the expanded shape table" if mr.template_base() != TMPL_EXPANDED else None)
        if why:
            raise SystemExit(f"--reach {room:02X}: {why}")
    for room in placed:
        fp = [[int(c) for c in line] for line in rows[room]["footprint"]]
        best = int(rows[room]["best_template"], 16)
        png = render_dir / rows[room]["render"] if render_dir else None
        if reach and room in reach:
            # Sub-rooms the player can reach, from --reach: draw the render's floor in those quadrants only.
            if not free:
                raise SystemExit(f"--reach {room:02X}: no free shape slot left")
            fp = [[v if quadrant_of(x * 4, y * 4) in reach[room] else 0 for x, v in enumerate(row)]
                  for y, row in enumerate(occupancy(png))]
            slot = free.pop(0)
            new_templates[f"{slot:02X}"] = [f"{w:04X}" for w in compose_template(fp, rom_data)]
            notes.append(f"reach {room:02X}: drew {'+'.join(QUADS[q] for q in sorted(reach[room]))} only, "
                         f"{shapes.get(room, best):02X} -> new shape {slot:02X}")
            shapes[room] = slot
            continue
        if room not in shapes:
            shapes[room] = best
            words = compose_template(fp, rom_data)
            made = iou(fp, template_pixels(map_chars(), words))
            if rows[room]["iou"] < MATCH and made > rows[room]["iou"] and free and mr.template_base() == TMPL_EXPANDED:
                slot = free.pop(0)
                new_templates[f"{slot:02X}"] = [f"{w:04X}" for w in words]
                shapes[room] = slot
                notes.append(f"new shape {slot:02X} for {room:02X} (overlap {rows[room]['iou']:.2f} -> {made:.2f})")
            continue
        # Hand-drawn quadrants that mostly cover pit or backdrop get the best walkable char instead.
        # Test against the whole render: the footprint drops quadrants it could not tie to content.
        floor = occupancy(png) if png and png.exists() else fp
        words, chars = list(mr.templates()[shapes[room]]), map_chars()
        made = compose_template(floor, rom_data)
        for q in range(4):
            px = [(y, x) for y, row in enumerate(word_pixels(chars, words[q])) for x, v in enumerate(row) if v]
            if px and sum(not floor[(q >> 1) * 8 + y][(q & 1) * 8 + x] for y, x in px) > PIT_SHARE * len(px):
                words[q] = made[q]
        if words != mr.templates()[shapes[room]] and free and mr.template_base() == TMPL_EXPANDED:
            slot = free.pop(0)
            new_templates[f"{slot:02X}"] = [f"{w:04X}" for w in words]
            notes.append(f"trimmed pits from {room:02X}: {shapes[room]:02X} -> new shape {slot:02X} "
                         f"(overlap {iou(fp, sil[shapes[room]]):.2f} -> {iou(fp, template_pixels(chars, words)):.2f})")
            shapes[room] = slot
        elif iou(fp, sil[shapes[room]]) < CLOSE and rows[room]["iou"] >= MATCH:
            # Hand-drawn shapes keep inner walls, gaps and pits the render misses; flag, never replace.
            notes.append(f"check {room:02X}: kept {shapes[room]:02X}, render suggests {best:02X} "
                         f"(overlap {iou(fp, sil[shapes[room]]):.2f} vs {rows[room]['iou']:.2f})")
    boss = cur["boss_room"] if cur["boss_room"] in placed else EMPTY
    return {"dungeon": dungeon_id, "slot": SLOTS[dungeon_id],
            "floors": [{"name": f["name"], "rows": [" ".join(f"{r:02X}" for r in f["grid"][y * 5:y * 5 + 5])
                                                    for y in range(5)]} for f in floors],
            "shapes": {f"{r:02X}": f"{t:02X}" for r, t in sorted(shapes.items())},
            "templates": new_templates, "boss": f"{boss:02X}", "notes": notes}


def spec_map(spec: dict) -> dict:
    floors = []
    for f in spec["floors"]:
        grid = [int(c, 16) for line in f["rows"] for c in line.split()]
        if len(grid) != 25:
            raise SystemExit(f"{spec['dungeon']} {f['name']}: a floor needs 5 rows of 5 rooms")
        floors.append({"name": f["name"], "grid": grid,
                       "templates": [int(spec["shapes"][f"{r:02X}"], 16) for r in grid if r != EMPTY]})
    basements = sum(f["name"].startswith("B") for f in floors)
    if [f["name"] for f in floors] != [floor_name(i, basements) for i in range(len(floors))]:
        raise SystemExit(f"{spec['dungeon']}: floors must run lowest first with no gaps")
    boss = int(spec["boss"], 16)
    where = [i for i, f in enumerate(floors) if boss != EMPTY and boss in f["grid"]]
    return {"basements": basements, "floors": floors, "boss_room": boss,
            "boss_floor": where[0] - basements if where else -1}


def map_blocks(m: dict) -> tuple[bytes, bytes]:
    return (b"".join(bytes(f["grid"]) for f in m["floors"]),
            b"".join(bytes(f["templates"]) for f in m["floors"]))


def repack(rom_data: bytes, maps: list[dict], full: bool = False) -> bytearray:
    """Write the 14 maps back. Each floor-grid run and each shape list stays in
    one piece (the game reads them contiguously). By default only a dungeon
    whose data changed moves: in place if it still fits, else into free space.
    full=True packs everything from the region start, the way yaze saves."""
    out, mr = bytearray(rom_data), MapRom(rom_data)
    old = [mr.dungeon(s) for s in range(14)]
    old_ptrs = [(mr.pc(mr.word(ROOM_PTRS + s * 2)), mr.pc(mr.word(TMPL_PTRS + s * 2))) for s in range(14)]
    taken = bytearray(DATA_END - DATA_START)  # 1 = byte belongs to a kept block
    for lo, hi in RESERVED:
        taken[lo - DATA_START:hi - DATA_START] = b"\1" * (hi - lo)
    plan = {}
    for slot, m in enumerate(maps):
        for kind, (new, cur) in enumerate(zip(map_blocks(m), map_blocks(old[slot]))):
            at = old_ptrs[slot][kind]
            if not full and len(new) <= len(cur):
                plan[slot, kind] = at
                taken[at - DATA_START:at - DATA_START + len(new)] = b"\1" * len(new)
    pos = DATA_START

    def alloc(size: int) -> int:
        nonlocal pos
        while pos + size <= DATA_END:
            if not any(taken[pos - DATA_START:pos - DATA_START + size]):
                taken[pos - DATA_START:pos - DATA_START + size] = b"\1" * size
                pos += size
                return pos - size
            pos += 1
        raise SystemExit(f"pause-map data overflows the bank $0A region (ends 0x{DATA_END:X})")

    def word(pc: int, value: int) -> None:
        out[pc], out[pc + 1] = value & 0xFF, value >> 8 & 0xFF

    for slot, m in enumerate(maps):
        uppers = len(m["floors"]) - m["basements"]
        out[FLOOR_COUNTS + slot * 2] = uppers << 4 | m["basements"]
        for kind, block in enumerate(map_blocks(m)):
            at = plan.get((slot, kind)) or alloc(len(block))
            out[at:at + len(block)] = block
            word((ROOM_PTRS, TMPL_PTRS)[kind] + slot * 2, 0x8000 | (at & 0x7FFF))
        word(BOSS_ROOMS + slot * 2, m["boss_room"])
        # Floor and icon visibility are separate bytes (bank_0A EE0A).
        # Generating map floors must preserve the original icon flags.
        out[BOSS_FLOORS + slot * 2] = m["boss_floor"] & 0xFF if m["boss_room"] != EMPTY else 0xFF
    return out


def region_of(pc: int) -> str:
    for start, size, name in ((FLOOR_COUNTS, 28, "floor counts"), (ROOM_PTRS, 28, "floor-grid pointers"),
                              (TMPL_PTRS, 28, "shape-list pointers"), (BOSS_ROOMS, 28, "boss rooms"),
                              (BOSS_FLOORS, 28, "boss floors (signed from 1F)")):
        if start <= pc < start + size:
            return name
    if TMPL_EXPANDED <= pc < TMPL_EXPANDED + 256 * 8:
        return "shape templates"
    return "floor grids and shape lists"


def byte_patch(before: bytes, after: bytes, label: str) -> dict:
    edits, pc = [], 0
    while pc < len(before):
        if before[pc] == after[pc]:
            pc += 1
            continue
        end = pc
        while end < len(before) and before[end] != after[end] and region_of(end) == region_of(pc):
            end += 1
        edits.append({"id": f"{label}-{len(edits) + 1:02d}", "pc": f"0x{pc:X}",
                      "snes": f"${pc >> 15:02X}{0x8000 | pc & 0x7FFF:04X}",
                      "before": before[pc:end].hex(" ").upper(), "after": after[pc:end].hex(" ").upper(),
                      "why": f"pause map: {region_of(pc)}"})
        pc = end
    return {"base_sha1": hashlib.sha1(before).hexdigest(), "edits": edits}


def render_maps(rom_data: bytes, slot: int, title: str):
    from PIL import Image, ImageDraw
    chars, mr = map_chars(), MapRom(rom_data)
    shapes, d = mr.templates(), mr.dungeon(slot)
    pal = [(20, 20, 32), (72, 72, 120), (130, 130, 190), (190, 190, 230), (250, 250, 250),
           (220, 100, 70), (100, 190, 100), (240, 210, 90)]
    cell, gap = 16 * 3, 12
    im = Image.new("RGB", (max(1, len(d["floors"])) * (5 * cell + gap) + gap, 5 * cell + 40), (36, 36, 44))
    draw = ImageDraw.Draw(im)
    draw.text((gap, 2), title, fill=(230, 230, 230))
    for fi, f in enumerate(d["floors"]):
        ox, tmpl = gap + fi * (5 * cell + gap), iter(f["templates"])
        draw.text((ox, 16), f["name"], fill=(230, 230, 150))
        for c, room in enumerate(f["grid"]):
            x0, y0 = ox + (c % 5) * cell, 30 + (c // 5) * cell
            draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], outline=(52, 52, 64))
            if room == EMPTY:
                continue
            px = template_pixels(chars, shapes[next(tmpl)])
            for y in range(16):
                for x in range(16):
                    if px[y][x]:
                        draw.rectangle([x0 + x * 3, y0 + y * 3, x0 + x * 3 + 2, y0 + y * 3 + 2], fill=pal[px[y][x] & 7])
            boss = (d["boss_icon_flags"] & 0x80 == 0 and room == d["boss_room"]
                    and fi == d["basements"] + d["boss_floor"])
            draw.text((x0 + 2, y0 + 1), f"{room:02X}", fill=(255, 90, 90) if boss else (255, 255, 255))
            if boss:
                draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], outline=(255, 70, 70), width=2)
    return im


def cmd_generate(args) -> int:
    from PIL import Image
    rom_data = args.rom.read_bytes()
    if args.spec and Path(args.spec).exists():
        if args.reach:
            raise SystemExit("--reach only applies when drafting a spec; edit the spec's shapes instead")
        spec = json.loads(Path(args.spec).read_text())
    else:
        spec = draft_spec(rom_data, args.dungeon, json.loads(Path(args.inventory).read_text()),
                          Path(args.inventory).parent, parse_reach(args.reach))
        if args.spec:
            Path(args.spec).write_text(json.dumps(spec, indent=1) + "\n")
            print(f"wrote draft spec {args.spec}; review it, then rerun to use it")
    for note in spec["notes"]:
        print(f"  {note}")
    maps = [MapRom(rom_data).dungeon(s) for s in range(14)]
    maps[spec["slot"]] = spec_map(spec)
    if args.fix_boss_floors:  # yaze stored floor indexes; vanilla expects floors from 1F
        for m in maps:
            where = [i for i, f in enumerate(m["floors"]) if m["boss_room"] != EMPTY and m["boss_room"] in f["grid"]]
            m["boss_floor"] = where[0] - m["basements"] if where else -1
    after = repack(rom_data, maps, full=args.full_repack)
    mr = MapRom(rom_data)
    referenced = referenced_templates(mr)
    for slot, words in spec.get("templates", {}).items():  # new shapes go in free expanded-table slots
        try:
            i, vals = int(slot, 16), [int(w, 16) for w in words]
        except ValueError:
            raise SystemExit(f"shape slot {slot}: slot and words must be hex") from None
        at = TMPL_EXPANDED + i * 8
        if (mr.template_base() != TMPL_EXPANDED or not 0 <= i < 256 or i in referenced
                or any(rom_data[at:at + 8])):
            raise SystemExit(f"shape slot {slot} is not a free, unused expanded-table slot")
        if len(vals) != 4 or not all(0 <= v <= 0xFFFF for v in vals):
            raise SystemExit(f"shape slot {slot}: needs four 16-bit words")
        after[at:at + 8] = b"".join(v.to_bytes(2, "little") for v in vals)
    after = bytes(after)
    patch = byte_patch(rom_data, after, f"map-{spec['dungeon'].lower()}")
    patch["source"] = f"Scripts/Generate/dungeon_maps.py generate --dungeon {spec['dungeon']}"
    Path(args.patch).write_text(json.dumps(patch, indent=1) + "\n")
    print(f"wrote {args.patch}: {len(patch['edits'])} edit(s), "
          f"{sum(len(e['after'].split()) for e in patch['edits'])} byte(s)")
    if args.preview:
        top = render_maps(rom_data, spec["slot"], f"{spec['dungeon']} now")
        bottom = render_maps(after, spec["slot"], f"{spec['dungeon']} generated")
        im = Image.new("RGB", (max(top.width, bottom.width), top.height + bottom.height), (36, 36, 44))
        im.paste(top, (0, 0))
        im.paste(bottom, (0, top.height))
        im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(args.preview)
        print(f"wrote {args.preview}")
    return 0


def cmd_preview(args) -> int:
    rom_data = args.rom.read_bytes()
    slot = SLOTS.get(args.dungeon.upper(), None)
    slot = int(args.dungeon) if slot is None else slot
    render_maps(rom_data, slot, f"{args.dungeon} ({args.rom.name})").save(args.out)
    print(f"wrote {args.out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("inventory", help="measure room shapes and match templates")
    inv.add_argument("--rom", type=Path, required=True, help="a COPY of the ROM")
    inv.add_argument("--gfx", type=Path, default=MAP_GFX, help="map shape art (default: %(default)s)")
    inv.add_argument("--out", required=True)
    inv.set_defaults(func=cmd_inventory)
    gen = sub.add_parser("generate", help="write one dungeon's pause-map byte patch")
    gen.add_argument("--rom", type=Path, required=True, help="a COPY of the ROM (read only)")
    gen.add_argument("--dungeon", required=True, choices=sorted(SLOTS))
    gen.add_argument("--inventory", help="inventory.json (needed to draft a spec)")
    gen.add_argument("--spec", help="spec JSON: used if it exists, else the draft is written here")
    gen.add_argument("--reach", action="append", default=[], metavar="ROOM=QUADS",
                     help="draw only these quadrants of a room, e.g. C8=SE or 40=NW+NE (repeatable)")
    gen.add_argument("--fix-boss-floors", action="store_true",
                     help="also rewrite every dungeon's boss floor as a signed floor from 1F")
    gen.add_argument("--full-repack", action="store_true",
                     help="repack all dungeons from the region start (yaze layout); default moves only changed data")
    gen.add_argument("--patch", required=True, help="output patch for apply_rom_byte_patch.py")
    gen.add_argument("--preview", help="output PNG: current map above, generated map below")
    gen.set_defaults(func=cmd_generate)
    pre = sub.add_parser("preview", help="draw one dungeon's pause map from a ROM")
    pre.add_argument("--rom", type=Path, required=True)
    pre.add_argument("--dungeon", required=True, help="registry id (D1, SOW) or slot number")
    pre.add_argument("--out", required=True)
    pre.set_defaults(func=cmd_preview)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
