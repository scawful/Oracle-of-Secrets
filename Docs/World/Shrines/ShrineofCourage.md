# Shrine of Courage

**Type:** Shrine
**Entrance ID(s):** 0x0C -> room 0x53, dungeon ID 0x09 (ZScream entrance table, bank $0F; checked 2026-09-26). Not shared: Fortress of Secrets is entrance 0x37 -> room 0x0C.
**Overworld Location:** OW 0x50
**Reward:** Pendant of Courage (item 0x38)
**Boss:** Vaati (designed as Vitreous reskin — NOT IMPLEMENTED)
**Dungeon Item:** Mirror Shield

---

## Overview

Shadow/temporal themed shrine in the Eon Abyss. Awards the Pendant of Courage, one of three pendants needed to forge the Master Sword.

**Status:** Stub — 7 rooms in dungeons.json (2026-09-26), no boss code, odd dungeon ID 0x09 (see Known Issues 1).

## Rooms (7, ROM connectivity 2026-09-26)

Room ownership from ROM connectivity (mutual doors, stair objects, warp tiles), room census 2026-09-26.
All seven rooms use blockset 7, palette 15 (same as D1). Rooms 0x16/0x26 are Zora Temple (D4);
0x23 is the Master Sword Cave (entrance 0x18).

| Room | Links (ROM) | Chest (z3ed) | Notes |
|------|-------------|--------------|-------|
| 0x07 | door S to 0x17; 4 warp tiles -> 0x63 | big chest, item 0x37 | pendant room |
| 0x17 | door N to 0x07; stair to 0x43 | item 0x25 | Opening it sets `$7EF364` (compass bits) = `$0008`; text "Big Chest Key" |
| 0x32 | stair to 0x33 | item 0x32 (big key) | tag1 0x32 |
| 0x33 | stairs to 0x32 and 0x43 | none | Lanmolas (vanilla leftover boss) |
| 0x43 | stairs to 0x17 and 0x33; door S to 0x53 | none | |
| 0x53 | door N to 0x43; exit door | big chest, item 0x06 (Mirror Shield) | entrance room (entrance 0x0C); big-key door |
| 0x63 | only in: 0x07 warp tiles (holewarp 0x63) | small key | tag1 0x32 (chest hidden until the tag fires); no door or stair object |

## Known Issues (2026-02-13)

1. **Dungeon ID 0x09 is odd** (every other dungeon ID is even). Runtime check on b28 (2026-09-26, headless Mesen2):
   - Small keys: slot = ID/2 = 4 (`$7EF380`), the same slot as dungeon ID 0x08 (entrance 0x24, Final Boss Route, room 0x15). Two keys taken in S3 showed as 2 keys in the Final Boss Route; one spent there left 1 key in S3.
   - Compass / big key / map bits: `DungeonMask` is read at byte offset 9, giving `$0008`, which is Dragon Ship's bit (ID 0x18). The 0x17 chest set `$7EF364 = $0008`. A D7 big key therefore opens S3 big-key doors (0x53, 0x17) and the reverse.
   - The pause-map room grids have no slot for an odd ID; rooms 0x33/0x43/0x53/0x63 sit in the Shrine of Power (0x06) grid.
   Needs a dungeon ID decision (not assigned here). The old note "entrance 0x0C shared with Fortress of Secrets" was a room/entrance mix-up: room 0x0C is the Fortress entrance room, entered by entrance 0x37.
2. **No Vaati boss implementation** — design docs describe Vitreous reskin but no ASM exists.
3. **Lanmolas in room 0x33 is a vanilla leftover** — not the intended S3 boss.
4. **Vaati reward path not implemented** — S3 Courage reward should come from Vaati boss clear, not a chest; Courage (0x38) is currently misassigned to S1 room 0x7A.
5. **dungeons.json SOC entry** — lists 0x07/0x17/0x32/0x33/0x43/0x53/0x63 with regenerated stairs/doors (2026-09-26).
6. **Room labels still carry vanilla names** — rooms 0x07, 0x17, 0x32 need Oracle-appropriate names.

---

## Room Layout

```
[To be mapped — 0x33/0x43/0x53/0x63 form a column in grid col 3, rows 3-6;
 0x32 is west of 0x33 (stairs); 0x07/0x17 are col 7, rows 0-1 (0x17 stairs to 0x43)]
```

---

## Generation Notes

**Generated with:** `location_mapper.py --location shrine_of_courage`
**Date:** 2026-02-04
**Updated:** 2026-02-13 (room assessment, ownership split from SOP, partial SOC entry); 2026-09-26 (entrance, room list and dungeon ID checked against the ROM and b28 runtime)
