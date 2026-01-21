# Water Collision System - Handoff Document

## Status: Partially Working, Needs Debugging

The water gate visual animation works correctly. The collision write hook is being called and executes without crashing. However, Link still cannot swim properly in all areas - collision values aren't being applied correctly to all tiles.

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
