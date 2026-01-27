# NPC Home & Dialogue Audit (Initial Pass)

**Date:** 2026-01-24
**Purpose:** Map NPC placements to rooms/screens and dialogue IDs; prioritize vanilla NPC reuse audit.
**Sources:** z3ed `overworld-list-sprites` (Roms/oos168_test2.sfc), `Core/messages.org`, `Sprites/NPCs/*.asm`, `Docs/Sheets/Oracle of Secrets Data Sheet - Custom Sprites.csv`
**Note:** `z3ed message-search` is now implemented and working; message text can be verified directly from ROM (`Roms/oos168_test2.sfc`).

---

## Overworld Screens (z3ed)

### OW 0x2D Tail Pond
**Unique sprite IDs seen:** `0xA0`, `0xEB`, `0x14`, `0x00`, `0x0D`, `0x77`

**Known mappings:**
- `0xA0` = Deku Scrub NPCs (withered Deku Scrub is here, main quest beat)
- `0x14` = Business Scrub (custom)
- `0x77` = Deku Leaf (custom)

**Unknown / vanilla mapping needed:**
- `0xEB`, `0x00`, `0x0D` (likely guards/ambient NPCs)

**Notes:** Mask Salesman is inside the shop (sprite ID `0xE8`), so it does not appear on the overworld list.

### OW 0x23 Wayward Village
**Unique sprite IDs seen:** `0x3F`, `0x0B`, `0x75`, `0x3D`, `0xF3`, `0x25`, `0xAC`

**Known mappings:**
- `0x25` = Village Dog (custom)

**Unknown / vanilla mapping needed:**
- `0x3F`, `0x0B`, `0x75`, `0x3D`, `0xF3`, `0xAC`

**Notes:** Village Elder is an interior NPC; overworld list does not include him.

### OW 0x0E Hall of Secrets (Exterior)
**Unique sprite IDs seen:** `0x51`, `0x0D`, `0x05`, `0x0A`, `0xCC`, `0xCD`

**Unknown / vanilla mapping needed:**
- `0x51`, `0x0D`, `0x05`, `0x0A`, `0xCC`, `0xCD`

**Notes:** Hall of Secrets interior (repurposed sanctuary) requires a room-level sprite audit (dungeon-list-sprites).

---

## Dialogue Mapping

### Village Elder (Wayward Village, interior)
- **Sprite file:** `Sprites/NPCs/village_elder.asm`
- **Message IDs:** `0x143` (first meeting), `0x019` (already met)
- **ROM text (oos168_test2.sfc):**
  - `0x143`: "Welcome, young one, to this... I will mark the spot on your map." (full text in `Docs/Sprites/NPCs/VillageElder.md`)
- **Status:** `0x143` is now in `Core/messages.org`.
- **Action:** Discuss progress-based updates (ties to Fortune Teller + Scrolls).

### Fortune Teller
- **Sprite file:** `Sprites/NPCs/fortune_teller.asm` (vanilla override)
- **Message IDs:** `0xEA`-`0xFD` (Fortune Teller hints)
- **Reference:** `Docs/Sprites/NPCs/FortuneTeller.md` now contains full text for all fortune messages.
**Note:** Fortune Teller appears in multiple entrances (LW/DW split); entrances can override blocksets/palettes for the same room.

### Librarian (Mermaid sprite)
- **Sprite file:** `Sprites/NPCs/mermaid.asm` (Librarian subtype)
- **Message IDs:** `0x012E`, `0x01A0`-`0x01A3` (scroll offer, translation, completion)
- **ROM text (oos168_test2.sfc):**
  - `0x012E`: "In your quest you may find... secret scrolls, bring them all to me for translation."
- **Status:** `0x012E` is now in `Core/messages.org`.
- **Reference:** `Docs/Sprites/NPCs/Mermaid.md` now contains full scroll message text.

---

## Interior Rooms (dungeon-list-sprites)
**Room ID source:** Entrance table (`kEntranceRoom` at `0x14813` in ROM) + entrance IDs from `Overworld/entrances.asm` (verified via `z3ed dungeon-get-entrance`).
### Hall of Secrets (Sanctuary Interior)
- **Entrance ID:** 0x02
- **Room ID:** 0x12
- **Sprites:**
  - 0x76 Zelda @ (8,17) subtype=0 layer=0
**Note:** Only Zelda appears in current sprite list; verify story flags for Maku Tree/Impa/Farore presence.

### Village Library (Librarian)
- **Entrance ID:** 0x49
- **Room ID:** 0x107
- **Sprites:**
  - 0x3B DashItem @ (27,8) subtype=0 layer=0
  - 0x6D Rat @ (23,27) subtype=0 layer=0
  - 0x6D Rat @ (24,27) subtype=0 layer=0
  - 0xF0 Librarian (Sprite_Mermaid subtype=2) @ (7,17) subtype=2 layer=0

### Village Mayor's House
- **Entrance ID:** 0x61
- **Room ID:** 0x119
- **Sprites:**
  - 0x29 Thief @ (7,5) subtype=0 layer=0
  - 0x07 ?FloorMove? @ (21,5) subtype=2 layer=0
  - 0x0B Chicken @ (9,26) subtype=0 layer=0
  - 0x0B Chicken @ (22,25) subtype=0 layer=0
**Note:** No obvious Village Elder sprite in this room; likely the Mayor/attendant interior.

### Village Elder House
- **Entrance ID:** 0x97
- **Room ID:** 0x202
- **Sprites:**
  - 0x3A Person?11,227 @ (31,24) subtype=27 layer=1
  - 0x29 Thief @ (16,2) subtype=17 layer=1
**Note:** Elder is likely a subtype on a repurposed sprite (confirm subtype mapping in `Sprites/NPCs.md` + sprite tables).

### Fortune Teller
- **Entrance ID:** 0x65/0x66
- **Room ID:** 0x122
- **Sprites:**
  - 0x31 FortuneTeller @ (7,24) subtype=0 layer=0
  - 0x31 FortuneTeller @ (23,24) subtype=0 layer=0

---

## Vanilla Sprite ID Mapping (yaze default names)
| Sprite ID | Default name (yaze) | Notes |
| --- | --- | --- |
| `0x00` | Raven | OW 0x2D unknown |
| `0x0A` | Octorock (four way | OW 0x0E unknown |
| `0x0B` | Chicken | OW 0x23; Mayor's House |
| `0x0D` | Buzzblock | OW 0x2D / 0x0E unknown |
| `0x05` | Pull Switch (unused | OW 0x0E unknown |
| `0x07` | Pull Switch (unused | Mayor's House (placeholder?) |
| `0x29` | Blind Hideout attendant | Mayor’s House + Elder House |
| `0x3A` | Half Magic Bat | Elder House (likely repurposed subtype) |
| `0x3D` | Signs? Chicken lady / Scared ladies | OW 0x23 unknown |
| `0x3F` | Tutorial Soldier | OW 0x23 unknown |
| `0x51` | Armos | OW 0x0E unknown |
| `0x75` | Bottle Salesman | OW 0x23 unknown |
| `0xAC` | Apple | OW 0x23 unknown |
| `0xCC` | Another part of Trinexx | OW 0x0E unknown |
| `0xCD` | Yet another part of Trinexx | OW 0x0E unknown |
| `0xEB` | Heart Piece | OW 0x2D unknown |
| `0xF3` | (unnamed) | OW 0x23 unknown |

## Room Metadata (Rooms & Entrances Sheet)
- Generated `Docs/Planning/room_metadata_audit.csv` from the sheet's room IDs using `z3ed dungeon-describe-room` on `Roms/oos168_test2.sfc`.
- Added `heuristic_tags` (name-based) to quickly flag boss/entrance/chest/etc. Treat as provisional until sprite/object audits land.
- **Update:** Room metadata refreshed after z3ed rebuild; blockset/spriteset/palette values now populated.
## Next Steps

1. Confirm Village Elder subtype mapping (0x3A / subtype=27) against sprite tables and update docs.
2. Discuss progress-based Village Elder dialogue updates and define triggers.
