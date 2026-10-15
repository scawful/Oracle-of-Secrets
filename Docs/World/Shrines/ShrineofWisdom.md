# Shrine of Wisdom

**Type:** Shrine
**Entrance ID(s):** 0x33
**Overworld Location:** OW 0x63
**Reward:** Pendant of Wisdom
**Boss:** None
**Dungeon Item:** Zora Flippers (beat sheet beat 14; decisions.org:151)

---

## Overview

Pendant of Wisdom chest is in room 0x7A (item 0x38, Core/patches.asm:13). Entrance 0x33 leads to room 0xC9 (inferred, `decisions.org:465`, verify in play). Room names are the `Docs/Dev/Planning/dungeons.json` labels (vanilla Swamp Palace room labels, not Oracle names). `dungeons.json` lists entrance 0x79 for room 0x7A; this page does not use it (`Overworld/entrances.asm:350` lists 0x33 for this shrine).

| Room | Name | Grid (row, col) | Notes |
|------|------|-----------------|-------|
| 0x7A | Pendant | 7, 10 | Pendant of Wisdom chest (item 0x38) |
| 0x8A | Penultimate | 8, 10 | |
| 0x9A | Flippers | 9, 10 | Zora Flippers (dungeon item) |
| 0xAA | Map Chest | 10, 10 | |
| 0xBA | Dark Antifairy / Key Pot | 11, 10 | |
| 0xC9 | Lower Entrance | 12, 9 | Entrance 0x33 (inferred) |
| 0xCA | Unidentified | 12, 10 | |


---

## Room Layout

```
Column 10, rows 7-12: 0x7A -> 0x8A -> 0x9A -> 0xAA -> 0xBA -> 0xCA (doors run south).
Room 0xC9 at row 12, col 9; door 0xC9 -> 0xCA (east).
```


---

## Generation Notes

**Generated with:** `location_mapper.py --location shrine_of_wisdom`

**Date:** 2026-02-04
