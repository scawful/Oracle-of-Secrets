# Water Collision System - Handoff Document

## Status: PARTIAL FIX - Horizontal Swimming Works

**2026-01-21 Testing Session:**
- Shifted collision data down 3 tiles (+20px Y offset compensation) - **WORKING**
- Room load hook disabled due to dungeon crashes - **WORKAROUND**
- Horizontal water strip allows swimming - **WORKING**
- Full water mask shape NOT covered - **NEEDS WORK**

### Current Build
- **Source ROM:** `oos168.sfc` (MD5: `2eb02125e1f72e773aaf04e048c2d097`)
- **Patched ROM:** `oos168x.sfc` (MD5: `6211297eeabb2f4b99040ba8cf2cce5a`)
- **Git Commit:** `32a9a3d` with uncommitted changes to `dungeons.asm`

---

## What Works

1. **Visual water fill animation** - HDMA/tilemap updates work perfectly
2. **Hook triggers correctly** - `WaterGate_FillComplete_Hook` at `$01F3D2` is called when water animation completes
3. **No crashes** - Fixed BRK crash caused by wrong processor state (`REP #$20` vs `REP #$30`)
4. **Partial swimming** - Link can swim in a thin strip of the water area

## What Doesn't Work

1. **Incomplete collision coverage** - Link gets stuck in parts of the water
2. **Can swim through floor** - Some floor tiles incorrectly have water collision

---

## Key Files

| File | Purpose |
|------|---------|
| `Dungeons/Collision/water_collision.asm` | Main collision system code |
| `Dungeons/dungeons.asm:165-167` | Hook installation (`JML WaterGate_FillComplete_Hook`) |
| `Dungeons/dungeons.asm:129-141` | `NewWaterOverlayData` - flood animation object data |
| `scripts/mesen_water_debug.lua` | Mesen2 debug overlay for testing |

---

## Technical Details

### Collision Map Layout
- **COLMAPA**: `$7F2000` - 64 bytes per row, 64 rows = 4096 bytes
- **COLMAPB**: `$7F3000` - Layer 2 collision
- **Collision types**: `$08` = deep water (swim), `$09` = shallow, `$00` = floor
- **Offset formula**: `offset = (Y_tile * 64) + X_tile`

### Room 0x27 Coordinates
The room has multiple coordinate systems that don't perfectly align:

1. **Water objects (0xD9) on Layer 1** - existing water at Y=39, X=5-57
2. **Flood overlay objects (0xC9)** - visual flood at Y=40, X=6-53
3. **Link's actual position** - debug showed Y=38-39 when standing in water

### Current Collision Data (174 tiles)
```
Y=12: X=40-47 (vertical channel) - 8 tiles
Y=28: X=40-46 (vertical channel) - 7 tiles
Y=38: X=5-57 (horizontal) - 53 tiles
Y=39: X=5-57 (horizontal) - 53 tiles
Y=40: X=5-57 (horizontal) - 53 tiles
```

---

## Bugs Fixed This Session

### 1. Bank Byte Storage (16-bit vs 8-bit)
**Problem**: Storing bank byte with 16-bit operation corrupted pointer
```asm
; WRONG - stores 16-bit value to $02-$03
REP #$30
LDA.w #WaterGate_Room27_Data>>16 : STA.b $02

; FIXED - store bank as 8-bit
SEP #$20
LDA.b #WaterGate_Room27_Data>>16 : STA.b $02
```

### 2. Processor State for LDY (BRK crash)
**Problem**: `LDY.w #$0000` assembled as 8-bit when index registers were 8-bit
```asm
; WRONG - only sets 16-bit accumulator
REP #$20
LDY.w #$0000  ; Assembles as LDY #$00, leaves garbage bytes

; FIXED - set 16-bit accumulator AND index
REP #$30
LDY.w #$0000
```

### 3. 16-bit Decrement Counter
**Problem**: `DEC.b $04` in 16-bit mode reads high byte from `$05`
```asm
; FIXED - clear high byte before loop
LDA.b [$00] : STA.b $04
STZ.b $05  ; Clear high byte for 16-bit decrement
```

---

## Debugging Tools

### Mesen2 Lua Script (`scripts/mesen_water_debug.lua`)
Displays real-time debug info:
- Room ID
- Link's world/local/tile position
- Collision offset being checked
- COLMAPA and COLMAPB values at Link's position
- Link state, submodule, action, speed
- Door flag ($0403) and deep water flag ($5D)

### Key RAM Addresses
| Address | Description |
|---------|-------------|
| `$7E0020-0023` | Link Y/X position (16-bit each) |
| `$7E002E` | Link state |
| `$7E001C` | Submodule |
| `$7E00A0` | Current room ID |
| `$7E0403` | Door/water gate flag |
| `$7E005D` | Deep water flag |
| `$7F2000+offset` | COLMAPA value |
| `$7F3000+offset` | COLMAPB value |

---

## Possible Issues to Investigate

### 1. Tile Coordinate Mismatch
The analyze_room.py tool shows water objects at certain positions, but Link's actual walkable tiles may be offset. Need to verify:
- Are water object coordinates in 8x8 pixel tiles or 16x16?
- Is there a consistent offset between object position and collision position?

### 2. Layer Confusion
Room has BG1 and BG2 layers. Water objects are on Layer 1 (BG2). Collision may need to account for which layer Link is on after jumping off ledge.

### 3. Collision Write Timing
The hook writes collision when flood animation completes. But:
- Is the collision map already initialized with floor values that override?
- Does the room reload collision from ROM data after our write?

### 4. Wrong Offset Calculation
Current formula: `offset = (Y * 64) + X`
- Verify this matches how the game calculates collision lookups
- Check if there's a base offset or room-specific adjustment

---

## Testing Procedure

1. Load Room 0x27 (Zora Temple water gate room)
2. Trigger the floor switch to start water fill
3. Wait for animation to complete
4. Run Mesen2 with `mesen_water_debug.lua` script
5. Walk into water and check:
   - COLMAPA should show `$08` (deep water)
   - Link should enter swim state
   - Movement should work in all water areas

---

## Next Steps

1. **Verify collision write is happening** - Add a visible indicator (like setting a known RAM byte) when hook runs
2. **Check collision lookup routine** - Find how the game reads from COLMAPA and verify offset calculation
3. **Compare with vanilla water room** - Look at Swamp Palace or similar to see how vanilla handles water collision
4. **Consider using vanilla collision tables** - The game may have existing water collision type mappings

---

## Relevant Vanilla Code

### FloodDam_Fill (`$01F3BD`)
The routine that runs during water fill animation. Our hook is at the end when it completes.

### RoomTag_WaterGate (`$01CB49`)
Triggers the water fill by setting `$11 = $0D` and configuring HDMA.

### Collision Lookup
Need to find where the game reads COLMAPA to determine Link's terrain type. This would confirm the offset formula.

---

## ROM Files

- `oos168_test2.sfc` - Clean ROM (ZScream OW v3) - use for analysis
- `oos91x.sfc` - Patched ROM with custom assembly

---

## Root Cause Analysis (2026-01-21)

### Discovery

The vanilla collision lookup routine (`TileDetect_MainHandler` at `$07D077`) adds **direction-based pixel offsets** to Link's position before checking tiles:

```asm
; From bank_07.asm disassembly
.calculate_offset
  LDA.b $22              ; Link's X
  CLC
  ADC.w .offset_x,Y      ; ADD OFFSET (+8 to +15 pixels)
  ...
  LDA.b $20              ; Link's Y
  CLC
  ADC.w .offset_y,Y      ; ADD OFFSET (+20 to +23 pixels)
```

For deep water checks (Y input = 5), the offsets are:
| Direction | Y Offset | X Offset |
|-----------|----------|----------|
| Up        | +20 px   | +8 px    |
| Down      | +20 px   | +8 px    |
| Left      | +23 px   | +0 px    |
| Right     | +23 px   | +15 px   |

### The Problem

**+20 pixels = ~2.5 tiles offset.** When Link is visually standing at tile Y=39, the game checks collision at tile Y=41-42. The original collision data at Y=38-40 was being checked when Link was at Y=35-38 - ABOVE the visual water.

### The Fix

Shifted all collision offsets down by 3 tiles in `water_collision.asm`:

| Old Row | New Row | Purpose |
|---------|---------|---------|
| Y=12    | Y=15    | Vertical channel |
| Y=28    | Y=31    | Vertical channel |
| Y=38    | Y=41    | Main water area |
| Y=39    | Y=42    | Main water area |
| Y=40    | Y=43    | Main water area |

### Verification Needed

1. Build patched ROM with new offsets
2. Test in Room 0x27:
   - Walk into water from all directions
   - Verify swim state triggers at visual water boundary
   - Test persistence on room re-entry
3. Update `mesen_water_debug.lua` to show BOTH raw tile and offset-adjusted tile

---

## Room Load Hook Issue (2026-01-21)

### Problem
The `Underworld_LoadRoom_ExitHook` at `$0188DF` caused **dungeon exit/re-entry crashes**.

### Root Cause
The hook relies on the Z flag from the instruction BEFORE the `JML`:
```asm
; At $0188DF - original code
BNE $0188C9     ; Branch if more torches (Z flag dependent)
SEP #$30
RTL

; Our hook replacement
JML Underworld_LoadRoom_ExitHook

; Hook code (water_collision.asm:187-197)
Underworld_LoadRoom_ExitHook:
{
  BNE .draw_next_torch    ; Z flag unreliable after JML!
  SEP #$30
  JSL WaterGate_CheckRoomEntry
  RTL
  .draw_next_torch
  JML $0188C9
}
```

### Workaround Applied
Commented out the hook in `Dungeons/dungeons.asm:169-173`:
```asm
; DISABLED FOR TESTING - suspected cause of dungeon crashes
; org $0188DF
; JML Underworld_LoadRoom_ExitHook
; NOP #1
```

### Effect
- **FIXED:** Dungeon exit/re-entry no longer crashes
- **BROKEN:** Water collision does NOT persist on room re-entry
- Players must re-trigger the floor switch each time they enter Room 0x27

### Proper Fix Needed
1. Save processor state (PHP) at hook entry
2. Restore state (PLP) before branch decision
3. Or: Check a memory flag instead of relying on CPU flags

---

## Known Menu Bugs (Separate Issue)

During testing, the following menu graphics issues were observed:

| Issue | Description |
|-------|-------------|
| Fishing Rod GFX | Missing from menu |
| Ring Box | Icons offset, frame corrupted |
| Magic Bag | Graphics messed up |
| Ocarina Song Frame | Frame corrupted, icons OK |

**These may predate the water collision work.** Relevant commits:
- `740571c` (Dec 8, 2025) - submenu upgrades
- `f508f9a` (Dec 8, 2025) - menu scroll fixes

**Files to investigate:**
- `Menu/menu_draw.asm` - Drawing functions
- `Menu/menu_gfx_table.asm` - Item graphics data
- `Menu/tilemaps/*.tilemap` - Binary tilemap data

---

## Debug Scripts Created

| Script | Purpose |
|--------|---------|
| `scripts/debug_transitions.lua` | Module/room tracking, stuck detection |
| `scripts/debug_crash_detector.lua` | Hook monitoring, invalid state detection |
| `scripts/debug_overworld.lua` | Overworld transitions, edge detection |

Load in Mesen2 via: **Tools → Run Script**
