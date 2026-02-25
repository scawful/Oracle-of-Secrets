# Shrine of Power

**Type:** Shrine
**Entrance ID(s):** 0x03, 0x05, 0x09, 0x0B (from OW 0x4B)
**Overworld Location:** OW 0x4B (Lupo Mountain)
**Reward:** Pendant of Power (item 0x3A)
**Boss:** None (intentional shrine design)
**Dungeon Item:** Power Glove

---

## Overview

Volcanic themed shrine in the Eon Abyss. Awards the Pendant of Power, one of three pendants needed to forge the Master Sword.

**Status:** Beta — rooms exist and connectivity is good, but pendant item data is still incorrect.

## Rooms (8 per all sources)

| Room | Name | Blockset | Palette | Notes |
|------|------|----------|---------|-------|
| 0x73 | Big Chest | 13 | 24 | |
| 0x74 | Map Chest | 13 | 24 | tag1=62 |
| 0x75 | Big Key Chest | 13 | 24 | tag1=23 (dark room) |
| 0x76 | Water Drain | 13 | 24 | Also listed under D4 Zora Temple in some sources |
| 0x83 | West Entrance | 13 | 24 | tag1=23 (dark room) |
| 0x84 | Main Entrance | 13 | 24 | Entrance 0x09 leads here |
| 0x85 | East Entrance | 13 | 24 | tag1=3 |
| 0x86 | Another Entrance | 13 | 24 | Entrance 0x05 leads here; tag1=23 (dark room) |

All rooms share blockset 13 / palette 24 (volcanic). Grid layout: 2x4 block at rows 7-8, cols 3-6.

## Known Issues (2026-02-13)

1. **Wrong pendant in chest** — Room 0x73 big chest contains Pendant of Wisdom (0x39) instead of Pendant of Power (0x3A). Needs yaze editor fix.
2. **Pendant of Power (0x3A) not in any chest** — chest data currently has no 0x3A placement anywhere in the ROM.
3. **Lava pit corner tile collision** — known collision issue per Release Roadmap.
4. **Room 0x76 ownership** — also listed as "Zora Temple (Water Drain)" in some data sources. Needs clarification.

---

## Room Layout

```
     Col 3    Col 4    Col 5    Col 6
Row 7: 0x73    0x74    0x75    0x76
Row 8: 0x83    0x84    0x85    0x86
```

Entrances at south row (0x83-0x86), chest/key rooms at north row (0x73-0x76).

---

## Generation Notes

**Generated with:** `location_mapper.py --location shrine_of_power`
**Date:** 2026-02-04
**Updated:** 2026-02-13 (room assessment, ownership resolution, pendant issue, no-boss decision)
