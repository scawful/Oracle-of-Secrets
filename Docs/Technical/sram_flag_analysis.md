# SRAM Flag Analysis & Inconsistencies

**Status:** ✅ FIXES APPLIED (2026-01-22)
**Date:** 2026-01-22
**Purpose:** Document SRAM flag usage, identify inconsistencies, and propose fixes

> **Note:** The fixes described in this document have been applied to `Core/sram.asm`.
> This document is retained for reference and future maintenance.

---

## Critical Issues Found

### 1. Duplicate/Conflicting Definitions in `sram.asm`

| Address | Definition 1 | Definition 2 | Location |
|---------|--------------|--------------|----------|
| `$7EF3C6` | `OOSPROG2` (line 28) | `PROGLITE` (line 416) | Both used! |
| `$7EF3C5` | `GameState` (line 7) | `GAMESTATE` (line 406) | Duplicate |
| `$7EF3C7` | `MapIcon` (line 44) | `MAPICON` (line 428) | Duplicate |
| `$7EF3D4` | `MakuTreeQuest` (line 32) | `UNUSED_7EF3D4` (line 477) | **CONFLICT!** |
| `$7EF3D6` | `OOSPROG` (line 18) | `UNUSED_7EF3D6` (line 479) | **CONFLICT!** |

**Impact:** `MakuTreeQuest` and `OOSPROG` are marked as "UNUSED" later in the file, but they're actively used!

### 2. Undocumented SRAM Addresses

These addresses are used in sprite code but NOT defined in `sram.asm`:

| Address | Used By | Purpose | Should Be Named |
|---------|---------|---------|-----------------|
| `$7EF300` | `kydrog.asm` | Kydrog/Farore removed from Maku area | `KydrogFaroreRemoved` |
| `$7EF301` | `deku_scrub.asm` | Deku Mask obtained (quest flag) | `DekuMaskObtained` |
| `$7EF302` | `zora_princess.asm` | Zora Mask obtained (quest flag) | `ZoraMaskObtained` |
| `$7EF303` | `patches.asm` | In cutscene flag | `InCutScene` (defined in patches.asm) |

### 3. Confusing Item vs Quest Flag Pattern

Some items have BOTH an inventory slot AND a separate quest flag:

| Item | Inventory Slot | Quest Flag | Notes |
|------|----------------|------------|-------|
| Zora Mask | `$7EF347` (ZoraMask) | `$7EF302` (undocumented) | Quest flag controls NPC behavior |
| Deku Mask | `$7EF349` (DekuMask) | `$7EF301` (undocumented) | Quest flag controls NPC behavior |

**Why this exists:** The inventory slot tracks if the item is equipped. The quest flag tracks progression (once set, NPCs change behavior permanently even if item is moved/unequipped).

### 4. Legacy ALTTP Comments Need Update

The `sram.asm` comments reference vanilla ALTTP storyline:

**Current (ALTTP):**
```asm
; Game state
;   0x00 - Very start; progress cannot be saved in this state
;   0x01 - Uncle reached
;   0x02 - Farore intro over | Zelda rescued
;   0x03 - Agahnim defeated
```

**Should be (Oracle of Secrets):**
```asm
; Game state
;   0x00 - Very start; progress cannot be saved in this state
;   0x01 - Reached Loom Beach (intro sequence)
;   0x02 - Kydrog encounter complete (sent to Eon Abyss)
;   0x03 - D7 complete (Farore rescued)
```

---

## SRAM Map (Corrected)

### Story Progression Block ($7EF300-30F)

| Address | Name | Purpose | Used By |
|---------|------|---------|---------|
| `$7EF300` | `KydrogFaroreRemoved` | Removes Kydrog/Farore from intro area | `kydrog.asm` |
| `$7EF301` | `DekuMaskObtained` | Deku Scrub quest complete | `deku_scrub.asm` |
| `$7EF302` | `ZoraMaskObtained` | Zora Princess quest complete | `zora_princess.asm` |
| `$7EF303` | `InCutScene` | Currently in cutscene | `patches.asm`, `kydrog.asm` |

### Main Progress Flags

| Address | Name | Bits | Purpose |
|---------|------|------|---------|
| `$7EF3C5` | `GameState` | Full byte | Major story milestones |
| `$7EF3C6` | `OOSPROG2` | Bitfield | Secondary story flags |
| `$7EF3D4` | `MakuTreeQuest` | Bit 0 | Met Maku Tree |
| `$7EF3D6` | `OOSPROG` | Bitfield | Primary story flags |
| `$7EF3D7` | `SideQuestProg` | Bitfield | Side quest progress 1 |
| `$7EF3D8` | `SideQuestProg2` | Bitfield | Side quest progress 2 |

### OOSPROG Bitfield ($7EF3D6)

| Bit | Flag | Meaning | Set By |
|-----|------|---------|--------|
| 0 | `i` | Intro over, met Maku Tree | `maku_tree.asm` |
| 1 | `h` | Hall of Secrets flag | `maku_tree.asm` |
| 2 | `p` | Pendant quest started | TBD |
| 3 | — | (unused) | — |
| 4 | `m` | Master Sword obtained | TBD |
| 5 | — | (unused) | — |
| 6 | — | (unused) | — |
| 7 | `f` | Fortress of Secrets complete | TBD |

### OOSPROG2 / PROGLITE Bitfield ($7EF3C6)

| Bit | Flag | Oracle Meaning | ALTTP Legacy |
|-----|------|----------------|--------------|
| 0 | `u` | Impa intro complete | Uncle visited |
| 1 | `s` | Sanctuary visited post-kidnap | Priest visited |
| 2 | `z` | (repurposed) Kydrog encounter done | Zelda brought to sanc |
| 3 | `h` | Impa left Link's house | Uncle left house |
| 4 | — | (unused) | — |
| 5 | `b` | Book of Secrets obtained | Book of Mudora |
| 6 | `f` | Fortune teller flip | Fortune teller flip |
| 7 | — | (unused) | — |

### SideQuestProg Bitfield ($7EF3D7)

| Bit | Flag | Meaning | Set By |
|-----|------|---------|--------|
| 0 | `n` | Met Mask Salesman | `mask_salesman.asm` |
| 1 | `c` | Found cursed Cucco | TBD |
| 2 | `w` | Found withering Deku Scrub | `deku_scrub.asm` |
| 3 | `m` | Got Mushroom from Toadstool | TBD |
| 4 | `o` | Old Man Mountain quest active | `old_man.asm` |
| 5 | `g` | Goron quest active | `goron.asm` |
| 6 | `d` | (reserved) | — |
| 7 | — | (unused) | — |

### SideQuestProg2 Bitfield ($7EF3D8)

| Bit | Flag | Meaning | Set By |
|-----|------|---------|--------|
| 0 | `r` | Ranch Girl transformed back | `ranch_girl.asm` |
| 1 | — | (unused) | — |
| 2 | `m` | Mask Salesman taught Song of Healing | `mask_salesman.asm` |
| 3 | `f` | Fortune teller visited | TBD |
| 4 | `s` | Deku Scrub soul freed | `deku_scrub.asm` |
| 5 | `t` | Tingle met | `tingle.asm` |
| 6 | `b` | Beanstalk grown (final) | TBD |
| 7 | — | (unused) | — |

---

## Sprite → SRAM Flag Cross-Reference

| Sprite | File | Flags Read | Flags Written |
|--------|------|------------|---------------|
| **Kydrog NPC** | `kydrog.asm` | `$7EF300` | `$7EF300`, `$7EF303`, `$7EF3C6`, `$7EF3CA`, `$7EF3CC` |
| **Maku Tree** | `maku_tree.asm` | `MakuTreeQuest`, `OOSPROG2` | `MakuTreeQuest`, `MapIcon`, `$7EF3D6` (OOSPROG) |
| **Farore** | `farore.asm` | `$7EF300`, `INDOORS` | `$B6`, `$7EF3C5`, `InCutScene` |
| **Zora Princess** | `zora_princess.asm` | `$7EF302`, `SongFlag` | `$7EF302` |
| **Zora (Sea)** | `zora.asm` | `ROOM`, `WORLDFLAG`, `Crystals`, `SprSubtype` | (none) |
| **Eon Zora** | `eon_zora.asm` | `AreaIndex` | `FOUNDRINGS` |
| **Eon Zora Elder** | `eon_zora_elder.asm` | (none) | (none - TODO: add dialogue) |
| **Deku Scrub** | `deku_scrub.asm` | `$7EF301`, `AreaIndex`, `SprSubtype`, `Crystals`, `SongFlag` | `$7EF301`, `SideQuestProg`, `SideQuestProg2`, `MapIcon` |
| **Mask Salesman** | `mask_salesman.asm` | `$7EF34C`, `$7EF348`, `$7EF352` | `$7EF34C`, `SideQuestProg`, `SideQuestProg2` |
| **Goron** | `goron.asm` | `RockMeat`, `WORLDFLAG`, `AreaIndex`, `$7EF280,X` | `$04C6` (mines trigger) |
| **Tingle** | `tingle.asm` | `TingleId`, `TingleMaps`, `$7EF360` (Rupees) | `TingleId`, `TingleMaps`, `$7EF360` |
| **Korok** | `korok.asm` | `$0AA5` (sprite sheet flag) | `$0AA5` |
| **Village Elder** | `village_elder.asm` | `OOSPROG` | `OOSPROG` |
| **Ranch Girl** | `ranch_girl.asm` | `$7EF34C` | `$7EF34C`, `SideQuestProg2` |
| **Impa** | `impa.asm` | `Sword`, `$7EF3D6` | `$7EF372`, `$7EF3D6`, `$7EF3C8`, `$7EF2A3` |

### Additional Flag Observations

| Flag | Location | Observation |
|------|----------|-------------|
| `$7EF3C5` | `farore.asm:220` | Set to 2 during FaroreFollowPlayer (GameState = crystals?) |
| `$04C6` | `goron.asm:112` | Non-SRAM flag for mine opening trigger |
| `$0AA5` | `korok.asm:86` | Non-SRAM flag for Korok sprite sheets loaded |
| `$B6` | `farore.asm:138,222` | Scratch RAM for Farore story state (not SRAM) |
| `SongFlag` | Multiple | Scratch RAM for detecting Song of Healing played |
| `InCutScene` | Multiple | Defined in patches.asm, controls player movement |

---

## Questions for Clarification

### 1. GameState Values
**Current understanding:**
- `0x00` = Start (can't save)
- `0x01` = After intro sequence
- `0x02` = After Kydrog encounter
- `0x03` = After D7?

**Question:** What are the actual Oracle of Secrets GameState milestones? The comments reference ALTTP values.

### 2. OOSPROG2 Bit 2 (`z`)
The ALTTP meaning is "Zelda brought to sanctuary."
**Question:** Is this repurposed for "Kydrog encounter done" or something else in Oracle of Secrets?

### 3. Quest Flag Pattern
**Question:** Should all mask/transformation items follow the pattern of having both:
- Inventory slot ($7EF34X)
- Quest flag ($7EF30X)

Or should we consolidate to just use the inventory slot?

### 4. Undocumented Flags
**Question:** Are there other undocumented flags in the $7EF300-30F range that are used but not listed here?

### 5. Village Elder OOSPROG Bit 4
The Village Elder sets `OOSPROG |= #$10`. This is bit 4 (`m` = Master Sword?).
**Question:** Is meeting the Village Elder supposed to be a Master Sword prerequisite, or is this flag being reused for something else?

---

## Suggested Fixes (✅ ALL APPLIED)

### 1. ✅ Add Missing Definitions to `sram.asm`

Added to top of sram.asm:
```asm
KydrogFaroreRemoved = $7EF300  ; Removes intro NPCs after Kydrog encounter
DekuMaskQuestDone   = $7EF301  ; Deku Scrub gave mask
ZoraMaskQuestDone   = $7EF302  ; Zora Princess gave mask
InCutSceneFlag      = $7EF303  ; In cutscene flag
```

### 2. ✅ Remove Conflicting UNUSED Markers

Removed and replaced with documentation comment:
- `UNUSED_7EF3D4` → Now documented as `MakuTreeQuest`
- `UNUSED_7EF3D6` → Now documented as `OOSPROG`
- `UNUSED_7EF3D5` → Renamed to `RESERVED_7EF3D5`

### 3. ✅ Consolidate Duplicate Definitions

Removed duplicates, kept canonical names:
- `GameState` at $7EF3C5 (removed `GAMESTATE`)
- `OOSPROG2` at $7EF3C6 (removed `PROGLITE`)
- `MapIcon` at $7EF3C7 (removed `MAPICON`)

### 4. ✅ Update Comments for Oracle of Secrets

Updated all comments to reflect Oracle of Secrets milestones:
- GameState values (Loom Beach, Kydrog encounter, D7 complete)
- OOSPROG/OOSPROG2 bit meanings
- MapIcon dungeon guidance (D1-D7 + Fortress)
- Crystals bitfield with dungeon mapping table
- SideQuestProg with sprite file cross-references

---

## Dungeon ID Reference (for Cross-Checking)

| Oracle Dungeon | ID | ALTTP Equivalent |
|----------------|----|-----------------|
| Mushroom Grotto | 0x0C | Palace of Darkness |
| Tail Palace | 0x0A | Swamp Palace |
| Kalyxo Castle | 0x10 | Skull Woods |
| Zora Temple | 0x16 | Thieves' Town |
| Glacia Estate | 0x12 | Ice Palace |
| Goron Mines | 0x0E | Misery Mire |
| Dragon Ship | 0x18 | Turtle Rock |

This mapping is important because `Crystals` bitfield uses ALTTP bit positions.
