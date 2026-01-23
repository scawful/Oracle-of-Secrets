# Lost Woods Camera Desync Issue

**Status:** OPEN - Requires deeper investigation
**Area:** Lost Woods (0x28-0x2A, 0x38-0x3A)
**Severity:** Medium (visual bug, gameplay not blocked)
**Date Found:** 2026-01-23
**Last Updated:** 2026-01-23

## Summary

Camera Y scroll value (`$7E00E7-E9`) does not properly update during and after area transitions in the Lost Woods. This causes the camera to lag behind Link's vertical position, potentially showing incorrect portions of the map.

## Observed Behavior

1. **Scroll drift accumulates**: When making wrong puzzle moves in Lost Woods (0x29), the puzzle code directly modifies scroll registers ($E7/$E9 for Y)
2. **Drift persists on exit**: When exiting Lost Woods, the accumulated drift isn't cleared
3. **Y offset grows**: After multiple wrong moves and exit, Y offset can reach 200+ pixels (should be ~112)

## Technical Details

**Scroll Registers:**
- `$7E00E1` - Scroll X Low (BG2)
- `$7E00E3` - Scroll X High (BG2)
- `$7E00E7` - Scroll Y Low (BG2)
- `$7E00E9` - Scroll Y High (BG2)

**Lost Woods Puzzle Code Modifications:**
```asm
; UP_CORRECT / CASE_UP - increments $E7, $E9 (Y scroll)
; DOWN_CORRECT / CASE_DOWN - decrements $E7, $E9 (Y scroll)
; LEFT_CORRECT / CASE_LEFT - increments $E1, $E3 (X scroll)
```

**Example trace after wrong moves and exit to 0x23:**
```
Area: 0x23  Mode: 0x09  Submode: 0x00
Link Y: 2771 (0x0AD3)
Scroll Y: 2566 (0x0A06)
Y Offset: 205 pixels  <- SHOULD BE ~112
```

## Reproduction Steps

1. Enter Lost Woods (Area 0x29)
2. Make several wrong puzzle moves (N/S repeatedly)
3. Exit east to 0x2A
4. Continue east to large map (0x23)
5. Observe camera Y offset is 200+ pixels

## Root Cause

The Lost Woods puzzle code directly modifies scroll registers to create a seamless looping effect. These modifications accumulate during wrong moves but are never reset when exiting.

## Failed Fix Attempts

### Attempt 1: Zero scroll at normalfinish (BEFORE transition)
**Result:** BROKEN - "made it much worse", broken map offset, shadow gone
**Reason:** Zeroing scroll before transition disrupts ZSCustomOverworld's scroll animation calculations

### Attempt 2: Recalculate scroll in Overworld_PlayerControl_Interupt (AFTER transition)
**Result:** BROKEN - Small-to-large transitions (0x2A→0x23) became severely corrupted
**Reason:** The recalculation function used camera boundaries which may not be set correctly during or right after transitions to large maps

### Attempt 3: Just clear flag, no recalculation
**Result:** Reverted to original bug - transitions work but Y offset persists (200+ pixels)

## Research Needed

To properly fix this, we need to understand:

1. **ZSCustomOverworld Transition Flow**
   - At what point are scroll values initialized during transitions?
   - How does the scroll animation work?
   - When are camera boundaries ($0600-$0606) set up?

2. **Small vs Large Map Handling**
   - How does the transition differ between small→small and small→large?
   - Why does the recalculation break large map transitions specifically?

3. **Vanilla Camera Behavior**
   - How does the vanilla game handle camera initialization after area changes?
   - What routine sets scroll from Link's position?

4. **Proper Hook Point**
   - Is there a point AFTER transitions complete where scroll can be safely recalculated?
   - Can we detect small vs large map destinations and apply different fixes?

## Key Files to Analyze

| File | Relevance |
|------|-----------|
| `Overworld/ZSCustomOverworld.asm` | Transition handling, camera bounds |
| `Overworld/lost_woods.asm` | Puzzle code, scroll modifications |
| Vanilla `$07E9D3` | ApplyLinksMovementToCamera |
| Vanilla `$02C0C3` | Overworld_SetCameraBounds |
| Vanilla transition routines | Scroll initialization |

## Workaround

Currently, the camera will naturally catch up to Link's position as he moves around in the new area. The desync is visual-only and doesn't block gameplay.

## Related Code

- `ZSCustomOverworld` transition routines
- `NewOverworld_SetCameraBounds` ($02C0C3)
- `OverworldScrollTransition_Interupt` ($02C02D)
- `Overworld_PlayerControl_Interupt` ($02A5D3)

## Test Tools

- `scripts/trace_lost_woods.py` - Monitor scroll and position values
- `scripts/overworld_explorer.py camera` - Manual camera check
