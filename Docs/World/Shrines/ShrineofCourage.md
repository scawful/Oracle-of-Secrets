# Shrine of Courage

**Type:** Shrine
**Entrance ID(s):** 0x0C (shared with Fortress of Secrets — needs resolution)
**Overworld Location:** OW 0x50
**Reward:** Pendant of Courage (item 0x38)
**Boss:** Vaati (designed as Vitreous reskin — NOT IMPLEMENTED)
**Dungeon Item:** Mirror Shield

---

## Overview

Shadow/temporal themed shrine in the Eon Abyss. Awards the Pendant of Courage, one of three pendants needed to forge the Master Sword.

**Status:** Stub — partial dungeons.json entry (0x33/0x43/0x53/0x63), no boss code, entrance shared with Fortress of Secrets.

## Rooms (8 per ROM)

Per `menu_map_names.asm` (source of truth):

| Room | Name | Blockset | Palette | Notes |
|------|------|----------|---------|-------|
| 0x07 | TBD | 7 | 15 | Vanilla: Tower of Hera (Moldorm Boss) |
| 0x16 | TBD | 7 | 15 | Vanilla: Zora Temple (Swimming Treadmill) |
| 0x23 | West Exit to Balcony | 7 | 15 | Custom name in labels |
| 0x26 | TBD | 7 | 15 | Vanilla: Zora Temple (Statue) |
| 0x33 | Lanmolas (Boss) | 7 | 15 | **Vanilla leftover boss — needs replacement with Vaati** |
| 0x43 | Torch Puzzle / Moving Wall | 7 | 15 | |
| 0x53 | Popos 2 / Beamos Hellway | 7 | 15 | |
| 0x63 | Final Section Entrance | 7 | 15 | tag1=50 (custom tag); entrance 0x62 from DW Beach |

## Known Issues (2026-02-13)

1. **Entrance 0x0C shared with Fortress of Secrets** — both dungeons use the same entrance ID from OW 0x50. Needs separate entrance or gating logic.
2. **No Vaati boss implementation** — design docs describe Vitreous reskin but no ASM exists.
3. **Lanmolas in room 0x33 is a vanilla leftover** — not the intended S3 boss.
4. **Vaati reward path not implemented** — S3 Courage reward should come from Vaati boss clear, not a chest; Courage (0x38) is currently misassigned to S1 room 0x7A.
5. **Only partial dungeons.json entry** — SOC now contains 0x33/0x43/0x53/0x63, but rooms 0x07/0x16/0x23/0x26 still need to be modeled with connectivity.
6. **Room labels still carry vanilla names** — rooms 0x07, 0x16, 0x26 need Oracle-appropriate names.

---

## Room Layout

```
[To be mapped — rooms form a vertical column in grid col 3, rows 3-6,
 plus scattered rooms at 0x07, 0x16, 0x23, 0x26]
```

---

## Generation Notes

**Generated with:** `location_mapper.py --location shrine_of_courage`
**Date:** 2026-02-04
**Updated:** 2026-02-13 (room assessment, ownership split from SOP, partial SOC entry)
