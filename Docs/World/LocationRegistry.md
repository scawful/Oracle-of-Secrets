# Oracle of Secrets - Location Registry

Master index of all indoor locations with entrance IDs.

**Source:** `Overworld/entrances.asm` (lines 293-421)
**Total Entrance Points:** 130+

---

## Location Summary

| Category | Count | Documentation |
|----------|-------|---------------|
| **Dungeons** | 7 | [Dungeons/](Dungeons/) |
| **Shrines** | 6 | [Shrines/](Shrines/) |
| **Caves/Grottos** | 25+ | [Caves/](Caves/) |
| **Houses** | 10+ | [Houses/](Houses/) |
| **Shops** | 4 | [Shops/](Shops/) |
| **Special Areas** | 5+ | [SpecialAreas/](SpecialAreas/) |

---

## Dungeons (7)

| ID | Name | OW Screen | Boss | Documentation |
|----|------|-----------|------|---------------|
| 0x26 | Mushroom Grotto (D1) | 0x10 | TBD | [Map](Dungeons/MushroomGrotto_Map.md) |
| 0x15 | Tail Palace (D2) | 0x2F | TBD | [Map](Dungeons/TailPalace_Map.md) |
| 0x28, 0x2B | Kalyxo Castle (D3) | 0x0B | TBD | [Map](Dungeons/KalyxoCastle_Map.md) |
| 0x25 | Zora Temple (D4) | 0x1E | TBD | [Map](Dungeons/ZoraTemple_Map.md) |
| 0x34 | Glacia Estate (D5) | 0x06 | TBD | [Map](Dungeons/GlaciaEstate_Map.md) |
| 0x27 | Goron Mines (D6) | 0x36 | King Dodongo | [Map](Dungeons/GoronMines_Map.md) |
| 0x35 | Dragon Ship (D7) | 0x30 | TBD | [Map](Dungeons/DragonShip_Map.md) |

**Additional Castle Entrances:**
- 0x2A - Kalyxo Castle Basement Route
- 0x32 - Kalyxo Castle Prison Entrance
- 0x0A - Kalyxo Castle Secret Courtyard

---

## Shrines (6)

| ID | Name | OW Screen | Reward | Documentation |
|----|------|-----------|--------|---------------|
| 0x03, 0x05, 0x09, 0x0B | Shrine of Power | 0x4B | Pendant of Power | [Map](Shrines/ShrineOfPower.md) |
| 0x0C | Shrine of Courage | 0x50 | Pendant of Courage | [Map](Shrines/ShrineOfCourage.md) |
| 0x33 | Shrine of Wisdom | 0x63 | Pendant of Wisdom | [Map](Shrines/ShrineOfWisdom.md) |
| TBD | Shrine of Origins | TBD | TBD | [Map](Shrines/ShrineOfOrigins.md) |
| TBD | Shrine of Sky | TBD | TBD | [Map](Shrines/ShrineOfSky.md) |
| TBD | Shrine of Sea | TBD | TBD | [Map](Shrines/ShrineOfSea.md) |

---

## Caves by Region

### Snowpeak Region

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x16 | Snow Mountain Cave East Peak | 0x07 | Passage | To 0x05 |
| 0x17 | Snow Mountain Cave to East Peak | 0x05 | Passage | To 0x07 |
| 0x1E | Snow Mountain Cave Start | 0x0D | Passage | Main cave system |
| 0x1F | Snow Mountain Cave Portal | 0x05 | Portal | Portal Room? |
| 0x20 | Snow Mountain Cave End | 0x0D | Passage | Cave exit |
| 0x30 | Snow Mountain East to West Peak | 0x07 | Passage | Peak connector |
| 0x31 | Snow Mountain West to East Peak | 0x04 | Passage | Peak connector |

### Beach/Coast Region

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x1A | Beach Cave Route | 0x32 | Passage | Beach connector |
| 0x1B | Beach Cave End | ?? | Passage | Exit point |
| 0x1C | Beach Cave Intro | 0x33 | Passage | Entry point |

### Kalyxo Field Region

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x21 | Kalyxo Field Cave Start | 0x25 | Passage | Field cave system |
| 0x22 | Kalyxo Field Cave River | 0x25 | Passage | River section |
| 0x23 | Kalyxo Field Cave End | 0x25 | Passage | Exit point |

### Forest/Toadstool Region

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x2C | Toadstool Woods Log Cave | 0x18 | Passage | Log entrance |
| 0x2E | Tail Palace Cave Route Start | 0x2D | Passage | To Tail Palace |
| 0x2F | Tail Palace Cave Route End | 0x2E | Passage | Palace connector |

### Mountain Region

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x06 | Mountain to Witch Shop Start | 0x15 | Passage | To Witch Shop |
| 0x07 | Mountain to Witch Shop End | 0x0D | Passage | From mountain |
| 0x51 | Rock Heart Piece Cave | 0x15 | Treasure | Heart Piece |

### Graveyard Region

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x5B | Hidden Grave | 0x0F | Secret | Hidden entrance |
| 0x5C | Graveyard Waterfall | 0x0F | Special | Waterfall cave |

### Special Caves

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x11 | 1/2 Magic Cave | 0x0B | Upgrade | Magic upgrade |
| 0x13 | Deluxe Fairy Fountain Pond | 0x15 | Fairy | Great Fairy |
| 0x14 | Deluxe Fairy Fountain Start | 0x15 | Fairy | Fountain entrance |
| 0x18-0x19 | Master Sword Cave | 0x40 | Special | Master Sword |
| 0x2D | Master Sword Cave (alt) | 0x40 | Special | Alternate entrance |
| 0x38 | Healing Fairy Cave (Exit) | 0x11 | Fairy | Exit only |
| 0x3A | Deluxe Fairy Fountain East | 0x1D | Fairy | East entrance |
| 0x3B | Deluxe Fairy Fountain South | 0x1D | Fairy | South entrance |
| 0x4F | Lava Cave Start | 0x43 | Passage | Lava region |
| 0x52 | Lava Cave End | 0x43 | Passage | Lava exit |
| 0x50 | Cave of Secrets | 0x0E | Special | Near Hall of Secrets |

---

## Houses

| ID | Name | OW Screen | Notable |
|----|------|-----------|---------|
| 0x01 | Link's House | 0x32 | Starting location |
| 0x0D | Mushroom House | 0x18 | Forest village |
| 0x0E | Old Woman House | 0x18 | Forest village |
| 0x3E | Ranch Shed | 0x00 | Lon Lon Ranch |
| 0x3F | Ocarina Girl's House | 0x00 | Ranch area |
| 0x40 | Sick Boy's House | 0x23 | Village |
| 0x42 | Village Tavern | 0x23 | Village |
| 0x44 | Village House | 0x23 | Village |
| 0x45 | Zora Princess House | 0x1E | Zora domain |
| 0x49 | Village Library | 0x23 | Village |
| 0x4B | Chicken House | 0x00 | Ranch area |
| 0x5F | Mines Shed | 0x36 | Goron Mines area |
| 0x60 | West Hotel | 0x0A | Western region |
| 0x61 | Village Mayor's House | 0x23 | Village |
| 0x64 | Smith's House | 0x22 | Blacksmith |
| 0x67 | Chest Minigame | 0x18 | Minigame |
| 0x68 | Bonzai House | 0x18 | Forest village |

---

## Shops (4)

| ID | Name | OW Screen | Inventory |
|----|------|-----------|-----------|
| 0x46 | Village Shop | 0x23 | General items |
| 0x4C | Witch Shop | 0x0D | Potions |
| 0x6B | Happy Mask Shop | 0x2D | Masks |
| 0x65-0x66 | Fortune Teller | ?? | Fortunes |

---

## Special Areas

| ID | Name | OW Screen | Purpose |
|----|------|-----------|---------|
| 0x02 | Hall of Secrets | 0x0E | Farore's Sanctuary |
| 0x12 | Hall of Secrets Pyramid Route | 0x02 | Secret path |
| 0x24 | Final Boss Route | 0x46 | Endgame path |
| 0x37 | Fortress of Secrets | 0x5E | Final dungeon |
| 0x4E | Zora Temple Waterfall | 0x1E | Temple entrance |
| 0x59 | Archery Minigame | 0x1A | Minigame |

---

## Special Overworlds

These are OW screens with special handling (from `special_areas.asm`):

| OW Screen | Name | Notes |
|-----------|------|-------|
| 0x80 | Maku Tree Area | Maku Tree sprite |
| 0x81 | Zora Falls West | Waterfall area |
| 0x82 | Zora Falls East | Waterfall area |
| 0x80 (variant) | Tree House | Special variant |

---

## Available Entrance IDs

The following IDs appear unused in `entrances.asm`:

```
0x04, 0x08, 0x0F, 0x10, 0x1D, 0x29, 0x36, 0x39, 0x3C, 0x3D,
0x41, 0x43, 0x47, 0x48, 0x4A, 0x4D, 0x53-0x58, 0x5A, 0x5D, 0x5E,
0x62, 0x63, 0x69, 0x6A, 0x6C-0x80
```

---

## Index Files

- [Dungeons/Dungeons.md](Dungeons/Dungeons.md) - Dungeon overview
- [Caves/index.md](Caves/index.md) - Cave directory
- [Houses/index.md](Houses/index.md) - House directory
- [Shops/index.md](Shops/index.md) - Shop directory
- [SpecialAreas/index.md](SpecialAreas/index.md) - Special area directory

---

## Generation Notes

**Generated from:** `Overworld/entrances.asm`
**Date:** 2026-02-04
**Last Updated:** 2026-02-04

### Data Source

Entrance ID comments are in `entrances.asm` lines 293-421:
```asm
; 0x00 - OW
; 0x01 - OW 32 - Link's House
; ...
```
