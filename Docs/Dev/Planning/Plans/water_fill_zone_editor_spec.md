# Water Fill Zone Editor — Feature Spec

**Date:** 2026-02-08
**Status:** Proposed
**Owner:** Codex (yaze side), Claude (ASM side)

## Problem

Water fill collision data for D4 Zora Temple is currently hardcoded in `water_collision.asm` as hand-authored tile offset tables (239 tiles for room 0x27, 168 tiles for room 0x25). Adding a new water room or adjusting fill patterns requires editing ASM data tables and recompiling the ROM. This doesn't scale and is error-prone.

## Goal

Let designers paint "water fill zones" in the yaze dungeon editor, and have the data serialized to ROM in a format the existing ASM runtime reads directly. Adding a water fill effect to any room becomes a visual authoring task, not an ASM task.

## Existing Infrastructure

### ASM Runtime (already works)

The water collision system in `Dungeons/Collision/water_collision.asm` already has a clean data-driven core:

**Data format** (per-room):
```
db <tile_count>           ; number of tiles to fill
dw <offset1>, <offset2>   ; each offset = Y*64 + X into $7F2000 collision map
...
```

**Apply routine** (`WaterGate_ApplyCollision`):
- Reads a 24-bit pointer to the data table
- Iterates tile_count entries
- Writes collision type `$08` (deep water) to both COLMAPA ($7F2000) and COLMAPB ($7F3000)
- Already fully general — doesn't care which room it's in

**Room lookup** (`WaterGateCollisionTable`):
- Currently a sparse table indexed by room ID × 4
- Contains pointers to per-room data (or $0000 for empty)

**SRAM persistence** (`WaterGateStates` at `$7EF411`):
- 8-bit bitfield, one bit per water room
- Bit 0 = room 0x27, Bit 1 = room 0x25, Bits 2-7 = reserved

### Yaze Editor (precedent)

The track collision generator (`zelda3/dungeon/track_collision_generator.h`) established the pattern:

```cpp
// Data structure
struct CustomCollisionMap {
  std::array<uint8_t, 64 * 64> tiles{};  // 64×64 collision grid
  bool has_data = false;
};

// Generate from room objects
absl::StatusOr<TrackCollisionResult> GenerateTrackCollision(Room*, options);

// Write to ROM
absl::Status WriteTrackCollision(Rom*, room_id, CustomCollisionMap&);

// Debug visualization
std::string VisualizeCollisionMap(const CustomCollisionMap&);
```

## Proposed Design

### 1. Data Structure (yaze C++)

```cpp
// In zelda3/dungeon/water_fill_zone.h

struct WaterFillZone {
  int room_id;
  std::vector<uint16_t> fill_offsets;  // Y*64+X for each tile
  uint8_t collision_type = 0x08;       // deep water (default)
  uint8_t sram_bit_index;              // which bit in $7EF411
};

struct WaterFillRegistry {
  std::vector<WaterFillZone> zones;    // all rooms with water fill

  // Serialize all zones to ROM data format
  absl::Status WriteToRom(Rom* rom);

  // Load existing zones from ROM
  static absl::StatusOr<WaterFillRegistry> LoadFromRom(Rom* rom);
};
```

### 2. Editor GUI (yaze dungeon editor)

Add a "Water Fill" overlay mode to the room collision editor:

- **Paint mode:** Click/drag tiles to mark them as "fills with water on activation"
- **Visual:** Painted tiles shown with blue overlay (semi-transparent)
- **Per-room toggle:** Room must have a water switch sprite (0x04 PullSwitch or 0x21 PushSwitch) to be eligible
- **SRAM bit assignment:** Auto-assigned from next available bit in $7EF411

This is similar to how the track collision generator's GUI has a "Generate" button — but instead of auto-generating from objects, the designer paints manually.

### 3. ROM Serialization

On save, the editor writes:

**Water Fill Table** (replaces `WaterGateCollisionTable` in ASM):
```
WaterFillTable:
  db <zone_count>                 ; number of rooms with water fill
  ; Per zone:
  db <room_id>                    ; which room
  db <sram_bit_mask>              ; which bit in $7EF411
  dw <data_offset>                ; offset to tile data (relative)
  ; ... repeat for each zone

  ; Tile data sections:
  db <tile_count>
  dw <offset1>, <offset2>, ...
  ; ... repeat for each zone
```

**ROM location:** Append after existing custom collision data in bank $25 (or wherever space allows). The pointer to the table head goes in a known ROM address that the ASM code reads.

### 4. ASM Runtime Changes

The current ASM hardcodes room ID checks. Replace with table-driven lookup:

```asm
; Current (hardcoded):
LDA.b $A0
CMP.b #$27 : BNE .check_room_25
  ; ... load Room27 data ...
CMP.b #$25 : BNE .done
  ; ... load Room25 data ...

; Proposed (table-driven):
LDA.b $A0
JSR WaterFill_FindRoomInTable  ; search table for current room
BCC .no_water_data             ; not found
; A = table entry index, $00-$02 = data pointer
JSR WaterGate_ApplyCollision   ; reuse existing routine
JSR WaterFill_SetPersistenceFlag  ; set SRAM bit from table
```

The `WaterGate_ApplyCollision` routine needs NO changes — it already takes a pointer and applies it generically.

## Room Registry (D4 Zora Temple — Corrected)

Previous analysis had wrong room set. The **actual D4 rooms** (16 total):

| Room | Oracle Name | Sprites | Key Feature |
|------|------------|---------|-------------|
| 0x06 | Arrghus Boss | 14 (boss+fuzz) | Boss arena, tag1=37 |
| 0x16 | Swimming Treadmill | 7 | Blobs, Chomp, FuzzyStack |
| 0x18 | Cave/Stairwell | 7 | Water bugs, connects 0x16↔outside |
| 0x25 | **Water Grate** | 2 | **PushSwitch + ZoraBaby already placed** |
| 0x26 | Statue Room | 0 | Holewarp from 0x36, to 0x66 |
| 0x27 | **Water Gate** | 2 | **PullSwitch + ZoraBaby already placed** |
| 0x28 | Entrance | 0 | Stairs to 0x38 (Key Pot) |
| 0x34 | Push Block / Pre-Big Key | 12 | Stairs to 0x25 |
| 0x35 | Big Key / BS | 11 | Stairs to 0x25, holewarp to 0x44 |
| 0x36 | Big Chest Room | 7 | Holewarp → 0x26 (Statue) |
| 0x37 | Map Chest / Water Fill | 6 | **tag1=39 (CustomTag)**, 4 stairs (hub) |
| 0x38 | Key Pot | 6 | Same 4 stairs as 0x37 (supertile pair) |
| 0x46 | Compass Chest | 6 | Stairs to 0x25 |
| 0x54 | Upstairs Pits | 6 | palette 1 (needs conversion?) |
| 0x66 | Hidden Chest / Hidden Door | 4 | palette 12, blockset 2 (needs conversion?) |
| 0x76 | Water Drain | 11 | palette 24, blockset 13 (needs conversion?) |

### Stair Connectivity (intra-D4)

```
0x28 (Entrance) ↕ 0x38 (Key Pot)
0x37 (Water Fill Hub) ↕ 0x28 (Entrance)
0x37 ↕ 0x06 (Boss)
0x38 ↕ 0x06 (Boss)
0x34 (Push Block) ↕ 0x25 (Water Grate)
0x35 (Big Key) ↕ 0x25 (Water Grate)
0x46 (Compass) ↕ 0x25 (Water Grate)
0x06 (Boss) ↕ 0x25 (Water Grate)
0x18 (Cave) ↕ 0x16 (Swimming Treadmill)
0x25 (Water Grate) ↕ 0x34 (Push Block)
```

### Holewarp Chain

```
0x36 (Big Chest) → fall → 0x26 (Statue Room) → fall → 0x66 (Hidden Chest)
```

### Water Rooms (current)

| Room | Switch | Collision Tiles | SRAM Bit |
|------|--------|----------------|----------|
| 0x27 | PullSwitch (0x04) | 239 | bit 0 |
| 0x25 | PushSwitch (0x21) | 168 | bit 1 |
| 0x76 | None (candidate for Water Dam) | — | bit 2 (future) |

## Migration Path

1. **Phase 1:** Read existing hardcoded data into the editor (parse `WaterGateCollisionTable` from ROM)
2. **Phase 2:** Add paint overlay to collision editor for water fill zones
3. **Phase 3:** Write painted zones back to ROM, replacing hardcoded ASM tables
4. **Phase 4:** Update ASM to use table-driven lookup instead of hardcoded room checks
5. **Phase 5:** Author "Water Dam" in room 0x76 using the editor (no ASM changes needed)

## Dependencies

- `zelda3/dungeon/custom_collision.h` — existing collision map infrastructure
- `zelda3/dungeon/track_collision_generator.h` — pattern for ROM write pipeline
- `core/hack_manifest.h` — for protected region tracking
- `water_collision.asm` — ASM runtime (minor refactor for table-driven lookup)

## Open Questions

1. Should water fill zones support collision types other than 0x08 (deep water)? E.g., 0x09 (shallow water) for partial fills.
2. Should the SRAM bit assignment be manual or auto-incremented?
3. Room 0x76 (Water Drain) has palette 24, blockset 13 — does it even look like a water room visually? Needs yaze visual check before planning the dam feature.
