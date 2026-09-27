# Oracle of Secrets underworld room census (rooms 0x000-0x127)

Date: 2026-09-26. Read-only analysis. No repo file or ROM was edited; no build or emulator run.
ROM analysed: copy of `Roms/oos168.sfc` (md5 `1afe31cf8d15f54db8234f48cc6825aa`) in the scratch dir.
Vanilla baseline: copy of `~/src/hobby/roms/Legend of Zelda, The - A Link to the Past (USA).sfc` (md5 `608c22b8ff930c62dc2de54bcd6eba72`, canonical US 1.0).
Per-room data: `room_census.csv` (296 rows) in this directory.

## Headline

| Count | Rooms |
|---|---|
| Total rooms | 296 |
| Used (Y): reached from a placed entrance or an ASM warp | 271 |
| Unclear (?): authored content but no verified path in | 7 (0x0F 0x30 0x4C 0x90 0x91 0x92 0x11D) |
| Not used (N): unreached and empty or vanilla leftover | 18 |
| Dungeon rooms (D1-D8, S1-S3, Origins, orphan 0x90-0x92) | 175 |
| Interiors (houses, shops, caves, fairy fountains) | 77 |
| Cutscene/special (Hall of Secrets, dream set, final route, final boss, hut) | 21 |
| Empty/placeholder (0 objects, or 1 object and 0-1 sprite) | 17 |
| Vanilla leftovers (unreached, >=90% vanilla objects) | 6 |
| **Free now (empty and unreached)** | **13** (11 high confidence, 2 with vanilla hardcode caveats) |
| **Reclaimable vanilla leftovers (unreached)** | **6** (0x01 0x10 0x30 0xA7 0x106 0x127) |
| Owner decision needed (orphan authored rooms, reachable empty shells) | 3 + 3 (0x90-0x92; 0x65 0xC0 0xD2) |

Upper bound for new content without deleting live content: 13 + 6 = 19 rooms. With owner approval for the 0x90-0x92 orphan and the 3 reachable shells: 25 rooms.

## 1. Method and commands

All `z3ed` commands ran against the scratch copies (`oos168_copy.sfc`, `vanilla_copy.sfc`). MD5 of the copy was re-checked after collection: unchanged.
The repo `Roms/oos168.sfc` was modified by another process at 15:38 during this analysis (new md5 `3b8875cc2ff6b1916e69b510e084a56c`; 28,308 bytes differ, all inside PC `0xE06B9`-`0xE7A36`, the message bank). Step 1 was re-run on a fresh copy (`oos168_copy2.sfc`): header, describe, sprite and chest output is identical for all 296 rooms. The census is valid for both versions.

1. Per room 0x00-0x127, both ROMs (`collect.sh`, 8-way parallel):
   - `z3ed dungeon-room-header --rom <rom> --room 0xNN --format json`
   - `z3ed dungeon-describe-room --rom <rom> --room 0xNN --include-objects --include-staircase-resolution --format json` (objects, doors, stair objects with resolved destination room, chests)
   - `z3ed dungeon-list-sprites --rom <rom> --room 0xNN --format json`
   - `z3ed dungeon-list-chests --rom <rom> --room 0xNN --format json`
   - Oracle only: `z3ed dungeon-list-custom-collision --rom <rom> --room 0xNN --nonzero --format json`
2. Entrances: `z3ed dungeon-get-entrance --entrance 0x00..0x84` and `--spawn 0..6`. Entrance 0x85+ returns garbage, so the table is 0x00-0x84.
3. Overworld placement: `z3ed overworld-list-warps --format json` (129 entrance slots, 19 hole slots). Cross-checked by reading the ROM tables directly (PC `0xDB96F`/`0xDBA71`/`0xDBB73` entrances, `0xDB800`/`0xDB826`/`0xDB84C` holes): identical to z3ed. 6 entrance slots are empty (pos `0xFFFF`). None of Oracle's 123 placed entrances matches a vanilla placement exactly.
4. ASM references: `asm_scan.py` greps `Core Dungeons Sprites Overworld Items Masks Menu Config Music` for compares against `$A0`/`RoomIndex`/`ROOM` and for `room $NN` comments; false positives removed by hand (`Items/ocarina.asm`, `Sprites/Bosses/lanmola.asm`, `Overworld/special_areas.asm` compare OW IDs; `Core/Cutscene/opening.asm:86` is room $104, not $04). Direct warps read from `Sprites/NPCs/maple.asm` (`Link_WarpToRoom .room: $61, $00, $31`), `Sprites/Enemies/custom_guard.asm` (entrance $32).
5. Vanilla hardcodes: grep of `; ROOM xxxx` comments in `~/src/hobby/usdasm/bank_*.asm`.
6. Graph (`analyze.py`, `build.py`):
   - Door edge: door on the room's outer edge (N `tile_y<=8`, S `>=50`, W `tile_x<=8`, E `>=50`) to room -16/+16/-1/+1. Exit types (0x04-0x16) and key-stair doors (0x20/0x22) excluded. Strong only if the neighbour has a door on the opposite edge within 3 tiles ("mutual").
   - Stair edge: `staircase_resolution.objects[].destination_room` (status `resolved`, or `vanilla_destination_room` when status is `custom_collision`).
   - Hole/warp edge: header `holewarp` when the room has pit objects (0x0A4, 0xFE6, pit edges 0x023-0x02E/0x06A/0x06B), layer-2 pit masks (0x0C2/0x0C3), warp tile 0xFCA, or custom-collision pit tiles. Rooms with tag 0x3A (Oracle `WarpTag`, `Dungeons/together_warp_tag.asm`) use header stair1-4 as the quadrant warp targets. A hole with only a "Holes" tag is weak.
   - Tier-A reach = BFS from placed-entrance start rooms + ASM warp rooms over strong edges. A hole/warp edge into a different blockset does not count (listed as anomaly instead).
   - Clusters = connected components over mutual doors, stairs (two-way or same blockset), and same-blockset holes/warps. Named by entrance and cross-checked with `Docs/Dev/Planning/dungeons.json` and `Docs/World/Dungeons/*_Map.md`.
7. Vanilla similarity: Jaccard of (object id, x, y, size) lists vs the vanilla ROM (`vanilla-obj-sim` in the CSV). ">= 0.90" = vanilla-unchanged content.

## 2. Per-dungeon / per-area table

Entrance format: `entrance -> start room (OW map)`. All values VERIFIED by `dungeon-get-entrance` + `overworld-list-warps` unless marked.

| Name | Entrance(s) | Rooms | Room list | Blockset.palette | Notes |
|---|---|---|---|---|---|
| D1 Mushroom Grotto | 0x26 -> 0x4A (OW10) | 15 | 09 0A 0B 19 1A 1B 2A 2B 3A 3B 4A 4B 5A 5B 6A | 7.15 (5A: 7.16) | 09/6A/5A reached through 0x3A tag-0x3A WarpTag (stair1-4 = 09,00,6A,09). 5B is D1 by connectivity (dungeons.json put it in FoS). |
| D2 Tail Palace | 0x15 -> 0x5F (OW2F) | 16 | 0E 1E 2E 3E 3F 4E 4F 5E 5F 6E 6F 7E 7F 8E 8F DE | 5.6 | dungeons.json says entrance 0x0E -> 0x0E: wrong. 0x1F (0 objects) is not part of D2. |
| D3 Kalyxo Castle | 0x28 -> 0x56, 0x2A -> 0x58, 0x2B -> 0x59, 0x0A -> 0x68, 0x32 -> 0x55 (all OW0B); 0x32 also from `custom_guard.asm` capture warp | 22 | 29 39 47 48 49 54 55 56 57 58 59 64 65 66 67 68 70 71 72 80 81 82 | 2.12 main; 1.1 prison (54 55 64 65 70 80); 3.14/3.2 basement (71 72 81 82) | 0x65 has doors only, 0 objects (reachable shell). dungeons.json lists only 9 rooms and puts 54/66 in D4. |
| D4 Zora Temple | 0x25 -> 0x28 (OW1E); 0x4E -> 0x10B (OW1E, waterfall) | 16 | 06 16 18 25 26 27 28 34 35 36 37 38 44 45 46 10B | 1.9 | Matches `ZoraTemple_Map.md` + Dam room 0x10B. dungeons.json's 54/66/76 belong to D3/D3/S2. Unplaced entrance 0x08 also targets 0x28. |
| D5 Glacia Estate | 0x34 -> 0xDB (OW06) | 19 | 9E 9F AC AD AE AF BB BC BD BE BF CB CC CD CE CF DB DC DD | 11.19 | 0xAC (boss, `twinrova.asm` checks $AC) has no doors or stair objects; entry path not found (INFERRED: pit from 0xAD/0xBC, both holewarp 0xAC). Matches dungeons.json. |
| D6 Goron Mines | 0x27 -> 0x98 (OW36) | 19 | 69 77 78 79 87 88 89 97 98 99 A8 A9 B8 B9 C8 D7 D8 D9 DA | 4.7 (C8: 4.32) | Lower floor reached by pit masks (89->D7, 97->B8, 98->B9). Matches dungeons.json. |
| D7 Dragon Ship | 0x35 -> 0xD6 (OW30) | 22 | A1 A2 A3 A4 A5 B1 B2 B3 B4 B5 B6 B7 C0 C1 C2 C3 C4 C5 C6 C7 D5 D6 | 9.5 deck; 3.5 interior; 9.30 lower (A1 A2 B1 B2 C0 C1 C2) | 0xC0 has doors only, 0 objects (reachable shell). dungeons.json lists 17 incl. 6 rooms that are the Master Sword Cave area. |
| D8 Fortress of Secrets | 0x37 -> 0x0C (OW5E) | 22 | 0C 0D 1C 1D 2D 3D 4C 4D 5C 5D 6B 6C 6D 7B 7C 7D 8B 8C 8D 9B 9C 9D | 14.3 | 0x4C reached only as 0x0D's holewarp (used=?). dungeons.json's 95/96/A6 are empty; A5 is D7; 5B is D1. |
| S1 Shrine of Wisdom | 0x33 -> 0xC9 (OW63) | 7 | 7A 8A 9A AA BA C9 CA | 8.13 | Pendant room 0x7A (chest patched in `Core/patches.asm`). |
| S2 Shrine of Power | 0x03 -> 0x76, 0x05 -> 0x86, 0x09 -> 0x84, 0x0B -> 0x83 (all OW4B) | 8 | 73 74 75 76 83 84 85 86 | 13.24 | 0x76 is S2 (not D4). |
| S3 Shrine of Courage | 0x0C -> 0x53 (OW50) | 7 | 07 17 32 33 43 53 63 | 7.15 (same as D1) | Separate component from D1. RC plan: room $07 holds the Courage chest. Entrance 0x0C dungeon ID is 0x09 (odd; see section 6). "Entrance 0x0C shared with FoS" in `ShrineofCourage.md` is a room/entrance mix-up: entrance 0x37 -> room 0x0C is FoS. |
| Shrine of Origins | 0x76 -> 0x05 (OW40) | 1 | 05 | 1.5 | Minish tag (0x36), `custom_tag.asm` checks $05. |
| Hall of Secrets | 0x02 -> 0x12 (OW0E); 0x12 -> 0x11 (OW02) | 7 | 11 12 21 22 40 41 42 | 3.17 | Also stair from 0x30 into 0x40. |
| Hyrule Castle dream set (Dream 1) | 0x29 -> 0x60 (OW7A, labelled "Available" in `entrances.asm`); `maple.asm` warp -> 0x61 | 6 | 50 51 52 60 61 62 | 0.12 (51: 2.12) | Vanilla castle rooms kept (sim 0.91-1.00). `hyrule_dream.asm` checks $51/$60. |
| Master Sword Cave / Final Boss Route | 0x18 -> 0x23 (OW40), 0x19 -> 0x24 (OW46), 0x2D -> 0x14 (OW40), 0x24 -> 0x15 (OW57) | 6 | 04 13 14 15 23 24 | 13.24 | 0x04 is near-vanilla (0.98). 0x14 pits -> 0x0D (FoS boss). dungeons.json filed these as D7. |
| Final boss room | hole 0x7B -> 0x00 (OW57); `maple.asm` dream Power warp -> 0x00 | 1 | 00 | 19.33 | Vanilla Ganon room reused (0.96). Holewarp 0x10. |
| Orphan mini-dungeon | none | 3 | 90 91 92 | 1.5 | Oracle-authored (sim 0.00): Moldorm + BlueOrb in 0x90 (tag 0x25 "defeat boss for prize", exit door), Titan's Mitt chest in 0x92. No entrance, no inbound edge. |
| Orphan pair | none | 2 | A0 B0 | 9.30 | 0xA0: 1 object; 0xB0: 0 objects, 3 doors. Door into 0xA1 is one-sided. |

Interiors (77 rooms, VERIFIED reach from placed entrances unless marked `?`): caves 0x2C 0x3C 0xE8 0xF8 (Deluxe Fairy Fountain), 0x2F, 0xD0-0xD2 (Lava Cave), 0xD3 0xD4 0xE4 0xE5 (Snow peak), 0xDF 0xEC 0xEE 0xEF 0xFF (Snow Mountain Cave), 0xE0 0xF0 0xF1 (Witch Shop cave), 0xE1 0xE2, 0xE3, 0xE6 0xE7, 0xEA 0xFA, 0xEB 0xFB 0xFC, 0xED 0xFD, 0xF6, 0xF9, 0xFE, 0x03, 0x08; houses/shops 0xF2 0xF3 0x103, 0xF4 0xF5, 0x100-0x105, 0x107-0x11C, 0x11D (?), 0x11E-0x126. 23 of these are vanilla-unchanged but placed on the OW (for example 0x10A, 0x115, 0x117, 0x11B, 0x122).

## 3. Counts

| Metric | Value | Source |
|---|---|---|
| Rooms | 296 | VERIFIED |
| Rooms whose z3ed-decoded header, objects, doors, sprites and chests all equal vanilla | 2 (0x10, 0xA7) | VERIFIED |
| Rooms with >= 90% vanilla objects | 37 | VERIFIED |
| Rooms with < 10% vanilla objects (rebuilt) | 199 | VERIFIED |
| Tier-A reachable | 270 (+0xAC by ASM/boss evidence = 271 used) | VERIFIED graph; 0xAC INFERRED |
| Used ? | 7 | INFERRED |
| Not used | 18 | VERIFIED unreached + VERIFIED content |
| Dungeon rooms by cluster | D1 15, D2 16, D3 22, D4 16, D5 19, D6 19, D7 22, D8 22, S1 7, S2 8, S3 7, Origins 1, orphan 3+2 | VERIFIED graph; names INFERRED from entrances + docs |
| Interiors | 77 | VERIFIED |
| Special | 21 (+0x31 reserved empty) | VERIFIED |

`Docs/Planning/room_metadata_audit.csv` (133 rows): blockset, palette, spriteset and object_count match the current ROM for all 133 rows (VERIFIED). `Docs/Dev/Planning/dungeons.json` room ownership is stale for D2, D3, D4, D7 and FoS (see section 2).

## 4. Free rooms for new content (ranked)

All below: no placed entrance leads in, no strong inbound edge, no Oracle ASM room reference (checked by `asm_scan.py`). "Pit-damage table" = vanilla `RoomsWithPitDamage` ($00:990C): pits there cost a heart and respawn instead of falling.

### High confidence (11)

| Room | Objects/sprites | Evidence | Caveat |
|---|---|---|---|
| 0x93 | 0/0 | unreached; no vanilla `; ROOM` hardcode | stair1 of D7 0xA2/0xA3 points here (stale header value, those rooms have no stair object to it) |
| 0x94 | 0/0 | unreached; vanilla empty clone | none |
| 0x95 | 0/0 | unreached; FoS header only | pit-damage table |
| 0x96 | 0/0 | unreached; FoS header only | pit-damage table; vanilla bank_04 per-room tile table |
| 0xA6 | 0/0 | unreached; FoS header only | 0xB6's north door is key-stairs, not a door into 0xA6 |
| 0xAB | 0/0 | unreached | vanilla follower trigger table ("to TT attic") |
| 0xE9 | 0/1 | unreached; vanilla empty clone | 1 sprite entry named "Ganon" (INFERRED: shared-pointer artifact) |
| 0xF7 | 0/1 | unreached; vanilla empty clone | same as 0xE9 |
| 0x1F | 0/1 | unreached; only a one-sided south door from 0x0F (the hut's exit edge) | vanilla chest-table and bank_04 entries for $1F |
| 0xB0 | 0/0 (3 doors) | unreached; pairs with 0xA0 | none |
| 0xA0 | 1/0 (2 doors) | unreached; door to 0xA1 one-sided | pit-damage table |

### Medium confidence: empty, but vanilla code special-cases the ID (2)

| Room | Evidence | Caveat |
|---|---|---|
| 0x02 | 0 objects, unreached | vanilla rain-SFX and follower checks for $0002 (`bank_02`, `bank_0A`, `bank_09`); `Menu/menu_hud.asm:612` keeps the vanilla rain check |
| 0x20 | 0 objects, unreached | 7 vanilla Agahnim hardcodes (boss, palette/animation set, tower exit) in `bank_02`, `bank_09`, `bank_1D`. Avoid unless those paths are neutralized. |

### Contiguous free blocks (grid adjacency matters only for same-floor door transitions; stairs can link any IDs)

1. Row 9-B, left: 0x93 0x94 0x95 0x96 (row), 0xA6 under 0x96, 0xA0 0xB0 column under 0x90. With owner approval to reclaim 0x90-0x92, this becomes a 10-room block 0x90-0x96 + 0xA0 + 0xA6 + 0xB0. 0x90 is the vanilla Vitreous boss slot (boss table and music hardcodes), which suits a boss floor. Best fit for the Sky Islands tower.
2. Column 0: 0x10 0x20 0x30 plus 0x01 0x02 (row 0). All vanilla leftovers or empty; carries the most vanilla hardcodes (Agahnim, Ganon evacuation music, rain).

## 5. Vanilla leftovers, possibly reclaimable (6)

| Room | Content | Evidence | Caveat |
|---|---|---|---|
| 0x10 | Ganon evacuation route, 71 objects | identical to vanilla; unreached; unplaced entrance 0x36 targets it | 0x00 (final boss room) holewarp = 0x10; vanilla music fade hardcode |
| 0xA7 | Hera fairy room, 18 objects | identical to vanilla; unreached; warp -> 0x17 (S3) | vanilla `is_hera_fairies` check |
| 0x01 | HC north corridor, 41 objects | sim 0.98; unreached; doors to 0x00/0x02 one-sided | header refs from 0x0A/0x0F/0x10/0x17 (stale values) |
| 0x106 | chest-game house, 56 objects | sim 0.98; unreached; unplaced entrances 0x47/0x48 target it | vanilla chest-game table (`bank_06`) |
| 0x127 | hammer-peg cave, 23 objects | sim 1.00; unreached; unplaced entrance 0x83 targets it | vanilla table (`bank_06`) |
| 0x30 | Agahnim tower chamber, 26 objects, AgahTalk sprite | sim 0.38 (partly edited); stair -> 0x40 (Hall of Secrets); unplaced entrance 0x75 targets it | vanilla song hardcode; partly edited, so ask before reclaiming (used=?) |

### Owner decision needed (not free today)

- 0x90-0x92: authored orphan mini-dungeon (Moldorm, Titan's Mitt chest). Either give it an entrance or reclaim it.
- 0x65 (D3 prison), 0xC0 (D7), 0xD2 (Lava Cave, 8 sprites): 0 objects but reachable through a mutual door. Free only if the door into them is removed, or build them out in place.
- 0x0F: Maple's Dream Hut (`maple.asm !DreamReturn_HutRoom = $000F`). Door $68 loads 0x11A instead (known gap in `decisions.org`). Not free.
- 0x31: Dream 3 placeholder, 0 objects, warp target in `maple.asm`. Not free.
- 0x11D: C-House, 6 chests (2 heart pieces), stair to D1 0x19, no verified way in.
- 0x4C: FoS room reached only as 0x0D's holewarp.

### Other capacity limits for new dungeons (VERIFIED values, impact INFERRED)

- Dungeon IDs used by placed entrances: 0x06 0x08 0x09 0x0A 0x0C 0x0E 0x10 0x12 0x14 0x16 0x18 0x1A. 0x04 (vanilla Eastern Palace) is used by no entrance. 0x00 and 0x02 are used only by unplaced entrances 0x81 and 0x04. The tower needs its own ID for keys, map and compass; 0x04 is the only clean slot.
- Unplaced entrance IDs (reusable): 0x00 0x04 0x08 0x36 0x47 0x48 0x5D 0x70 0x72 0x73 0x74 0x75 0x77 0x78 0x79 0x7A 0x7E 0x81 0x83. 0x78-0x7A and 0x81 appear in the uncalled `Link_FallIntoDungeon` table in `maple.asm`.
- OW entrance table: 6 of 129 slots empty. OW hole table: 1 of 19 slots empty, and 0x80 holes repeat positions.

## 6. Anomalies found (INFERRED, not runtime-tested)

Cross-dungeon holewarps (the pit objects exist and the header destination is in another dungeon):
- D3 0x47, 0x49 (pits 0xFE6) -> 0x07 (S3 pendant room)
- D3 0x67 (pits 0x0A4) -> 0x05 (Shrine of Origins)
- D5 0xCB (pits 0x0A4) -> 0x0B (D1)
- D6 0xB9, 0xD7, 0xD8 (layer-2 pit masks) -> 0x05 (Shrine of Origins). Same class as the fixed 0xB8 -> 0x00 bug in `Core/patches.asm`.
- S2 0x76 (pit masks) -> 0x03; D2 0xDE (pit masks) -> 0x06 (D4 boss); 0x123 (pit edges) -> 0x06; 0x3C -> 0x0E (D2 entrance); 0x14 -> 0x0D (FoS boss; may be the intended final route)
- D1 0x19 (tag 0x21 floor puzzle, no pit object) -> 0x07 (S3)

Other:
- Entrance 0x0C (S3) has dungeon ID 0x09. Every other dungeon ID is even.
- Cross-area staircases: 0x119 (Village Mayor's House) -> 0x1D (FoS final hallway); 0x11D -> 0x19 (D1); 0x30 -> 0x40 (Hall of Secrets).
- Sprite lists of empty rooms 0x1F, 0xE9, 0xF7 each hold one "Ganon" entry.

## 7. What could not be verified

1. Runtime reachability. No emulator run. Tier-A reach is a static graph. Doorless walk-off edges, scripted warps outside the scanned ASM, tag-driven holes and custom-collision behaviour are not modelled beyond the rules above.
2. Whether each placed OW entrance can be reached in play. Entrances on Abyss maps (0x6F 0x70 0x73 0x75 0x76 0x7A, for example 0x29 -> 0x60 on OW 0x7A) are counted as used because they are in the table.
3. How the D5 boss room 0xAC is entered. It has no doors or stair objects; the pit path from 0xAD/0xBC is inferred.
4. Pit detection: layer-2 pit masks (0x0C2/0x0C3) are treated as pits. Some may be decorative, for example D6 rails.
5. Object equality uses z3ed-decoded (id, x, y, size), not raw object-stream bytes. Layer is not compared. "Identical to vanilla" means identical in that decoded form.
6. The ASM scan is lexical. A room ID loaded from a data table without a "room" comment or an `$A0` compare would be missed. `Util/` and `ZSCustomOverworld.asm` were excluded as OW or duplicate code.
7. Cluster names come from entrance comments in `Overworld/entrances.asm`, the docs and `decisions.org`. The room ownership itself comes only from ROM connectivity.
8. `maple.asm` says entrance $68 lands in room $0F; the ROM entrance 0x68 -> 0x11A. `decisions.org` records this as a known gap. The census follows the ROM.
9. Free space for room object and sprite data (bank capacity) is not measured. `z3ed dungeon-stream-plan` needs a manifest.
