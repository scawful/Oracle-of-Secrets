# dungeon_contact_translator.py (v0)

Stage 2 of the dungeon design pipeline (design packet -> **translator** -> checker ->
render-review gate -> editor round trip -> gated write + native).

The translator copies a **measured** wall-cutting stair contact to a new anchor. It keeps
object IDs (including extended `0xFxx`), sizes, stream list and relative order exactly.
It never invents a stair: anything not in the library returns `UNSUPPORTED`.

## Library (`data/dungeon_contact_library.json`)

| Family | Source | Members in stream order | Facing |
|---|---|---|---|
| `oracle_cc_spiral_wall_cut` | Oracle room 0x0CC | wall `0x001` (21), flair `0x0B6` (45), spiral `0x139` (52) | north |
| `hallows_0da_south_stair_wall_cut` | All Hallows Eve 0x0DA | wall `0x004` (56), stair `0xF9D` (57) | south |
| `alttp_61_dais_cutin_north` | ALTTP 0x061 | corners/walls 20-24, stair `0x132` (52) | north |

Each family records its reference trace (relative to the
`dungeon_wall_completion_2026-11-05` handoff folder) and that trace's sha256. Anchor =
stair member position, tile8 units. Excluded neighbours are listed with reasons.

## Commands

```bash
# 1. packet -> ordered object list (exit 1 + empty list on UNSUPPORTED)
python3 Scripts/Rooms/dungeon_contact_translator.py translate --packet P.json --out O.json
# 2. write to a PRIVATE scratch copy through the guarded z3ed writer (dry run without --write)
python3 Scripts/Rooms/dungeon_contact_translator.py apply --objects O.json --rom scratch.sfc --write
# 3. after `z3ed dungeon-object-validate --trace-out T.json`: checker contract
python3 Scripts/Rooms/dungeon_contact_translator.py contract --objects O.json \
  --candidate-trace T.json --require stair --out C.json
python3 Scripts/Rooms/dungeon_layout_preflight.py --contract C.json --trace T.json
```

Packet: `{"schema_version":1,"room_id":"0xDA","contacts":[{"name":"m","family":"...","anchor":[x,y]}]}`.
Optional `facing`, `rotation`, `mirror` exist only to be refused: v0 copies source
orientation. `--relocate-source` (packet room = source room) removes the source members
(highest index first) before placing, so a full room keeps its byte count.

`apply` refuses any path with a `Roms` or `*.yazeproj` part and any ROM whose sha256 starts
with `e1e6fb5b`. It only calls `z3ed dungeon-remove-object` (expect-guarded) and
`dungeon-place-object`; it never encodes room bytes.

## Checker: `stair_mouth` boundaries

`--require all` adds a `wall_boundaries` entry `{"kind": "stair_mouth", "family": ...}`.
The checker (`dungeon_layout_preflight.py`) passes it only when:

1. the family is in this library (fixed repo path; a contract cannot add families);
2. the reference trace's member writes hash to the family's `contact_sha256`;
3. the candidate is a rigid copy: one shared offset, same IDs/sizes/lists/tile words
   (rotated or mirrored copies are `UNSUPPORTED`);
4. the stair draws after the walls it cuts (else `BLOCKED STAIR_MOUTH_ORDER`);
5. every mouth cell's final owner is the stair (else `BLOCKED STAIR_MOUTH_OWNER`), and
   other contact cells keep their measured owners (`WALL_OVERWRITTEN`).

Not certified: where the cut wall run meets the rest of the room (`ends_certified:
false`, listed under `excluded`). Closed-cycle boundaries are unchanged. Fixtures:
`tests/fixtures/dungeon_layout/contact_translator/`.

## Controls (2026-11-08, private scratch ROMs)

| Control | Result |
|---|---|
| Round trip, Oracle 0xCC (+0,+8) | stair PASS; crop 32/32 cells pixel-equal |
| Round trip, Hallows 0xDA (+8,+0), entrance 0x08 | stair PASS; crop 56/56 cells |
| Round trip, ALTTP 0x61 (-1,-7) | stair PASS; crop 90/92 cells (see below) |
| Wrong order, Hallows (stair before wall) | checker BLOCKED `ASSEMBLY_MISMATCH`; render shows a closed mouth |
| Unsupported (facing north, rotation 90, mirror, unknown family) | translate exit 1, `UNSUPPORTED`, no objects |

ALTTP: 2 corner cells (source 5,22/5,23) render differently after the move although the
traced final owner and tile words (`0x108`, tiles `0x53`/`0x43`) are identical. The
difference is renderer content outside the object trace.

Test: `python3 -m unittest Tests.test_dungeon_contact_translator`.
