# L/R Hookshot/Goldstar Swap Fix

**Status:** UNTESTED
**Date:** 2026-01-21
**Files Modified:**
- `Masks/mask_routines.asm` (lines 1356-1382)
- `Items/goldstar.asm` (lines 1001-1017)

---

## Summary

Fixed the L/R button swap for Hookshot/Goldstar items during gameplay.

### Changes Made

1. **Added `CheckNewLButtonPress`** - New routine that mirrors `CheckNewRButtonPress` but checks L button (bit $20 of $F6)

2. **Fixed input clearing bug** - Changed `STZ $F6` to `AND #$EF/$DF` to only clear the specific button pressed, preventing regressions with other systems that also read `$F6`

3. **Updated `CheckForSwitchToGoldstar`** - Now checks both L and R buttons

### Before (broken)
```asm
CheckForSwitchToGoldstar:
  JSL CheckNewRButtonPress : BEQ .continue  ; Only R worked
  ...
```

### After (fixed)
```asm
CheckForSwitchToGoldstar:
  JSL CheckNewRButtonPress : BCS .do_swap
  JSL CheckNewLButtonPress : BEQ .continue  ; Now L also works
  .do_swap
  ...
```

---

## Key Memory Addresses

| Address | Name | Description |
|---------|------|-------------|
| `$7E00F6` | F6 | New button inputs (AXLR) - current frame only |
| `$7EF342` | Hookshot | SRAM: $01=hookshot, $02=has both hookshot+goldstar |
| `$7E0739` | GoldstarOrHookshot | Which is currently equipped: $01=hookshot, $02=goldstar |
| `$7E0202` | Menu cursor | Current menu selection (hookshot slot = $03) |

### Input Bits ($F6)
- Bit 4 ($10) = R button
- Bit 5 ($20) = L button
- Bit 6 ($40) = X button
- Bit 7 ($80) = A button

---

## Testing Requirements

### Prerequisites
1. Save state with both Hookshot AND Goldstar acquired (`$7EF342 == $02`)
2. Hookshot/Goldstar equipped in Y-item slot (`$7E0202 == $03`)
3. Outside of menu (normal gameplay)

### Test Cases

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 1 | R button swap | Press R during gameplay | Swaps between Hookshot/Goldstar |
| 2 | L button swap | Press L during gameplay | Swaps between Hookshot/Goldstar |
| 3 | No regression: masks | Use mask item with R | Mask transformation works |
| 4 | No regression: menu L/R | Press L/R in menu | Menu scroll works |
| 5 | Rapid toggle | Press L then R quickly | Both swaps register |

### Regression Checks
- Menu navigation still works (other systems reading $F6)
- Mask transformation still works (uses `CheckNewRButtonPress`)
- No stuck inputs or missed button presses

---

## Save State Requirements

Need save states that meet these criteria:

| State | Requirements | Current Coverage |
|-------|--------------|------------------|
| Hookshot only | `$7EF342 == $01` | Unknown |
| Both items | `$7EF342 == $02` | **Required for test** |
| Hookshot equipped | `$7E0202 == $03` | Unknown |

---

## Mesen2 Testing Commands

```lua
-- Check if player has both items
emu.read(0x7EF342, emu.memType.snesMemory) -- Should be $02

-- Check which is currently equipped
emu.read(0x7E0739, emu.memType.snesMemory) -- $01=hookshot, $02=goldstar

-- Check current menu selection
emu.read(0x7E0202, emu.memType.snesMemory) -- $03=hookshot slot

-- Watch for button press handling
emu.read(0x7E00F6, emu.memType.snesMemory) -- New inputs this frame
```

---

## Next Steps

1. [ ] Build ROM with fix applied
2. [ ] Identify/create save state with both Hookshot+Goldstar
3. [ ] Run through test matrix
4. [ ] Verify no regressions in other L/R uses
5. [ ] Mark as TESTED once verified
