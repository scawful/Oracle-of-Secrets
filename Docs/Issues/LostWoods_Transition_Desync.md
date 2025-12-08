# Issue: Lost Woods Transition Coordinate Desync

## Status: Active / Low Priority
**Created:** March 2026
**Impact:** Visual/Gameplay discontinuity when exiting the Lost Woods (Area 0x29) back to the West (0x28).

## Problem Description
The custom Lost Woods puzzle uses a coordinate manipulation trick (`INC/DEC $21`, `INC/DEC $E7`) to simulate an infinite loop.
-   **Symptoms:**
    -   When completing the puzzle (Exit East -> 0x2A), the fix implemented (`LostWoods_ResetCoordinates`) correctly snaps Link to the left edge of the new screen, preventing him from skipping the map.
    -   **Regression:** When *returning* to the previous map (Exit West -> 0x28), Link may appear at incorrect coordinates or the camera may be misaligned relative to the player.
    -   The "Snapping" logic forces Link's X/Y to the base of Area 0x29 (e.g., X=0x0200). However, the transition logic in `ZSCustomOverworld.asm` uses these coordinates to calculate the *destination* position in the new area. If the snap happens too early or incorrectly, the destination calculation (Start X - Offset) might underflow or misalign.

## Technical Analysis

### Custom Logic (`lost_woods.asm`)
The puzzle modifies:
-   `$21` / `$23`: Link's High-Byte Coordinates (World Grid Position).
-   `$E1` / `$E7` / `$E9`: Overlay and BG Scroll Registers.

This desynchronizes the "Visible" position from the "Logical" position expected by the standard Overworld engine.

### ZSOW Transition Logic
`OverworldHandleTransitions` in `ZSCustomOverworld.asm` relies on:
-   `$20` / `$22`: Link's 16-bit absolute coordinates.
-   `Pool_OverworldTransitionPositionX/Y`: Lookup tables for screen boundaries.

### Root Cause Hypothesis
1.  **Coordinate Mismatch:** The `LostWoods_ResetCoordinates` routine snaps Link to `X=0x0200` (Left edge of 0x29).
2.  **Transition Calc:** When moving West to 0x28, the engine expects Link to be crossing the boundary.
3.  **Vanilla vs. Custom:** Vanilla ALTTP does not use infinite looping coordinates in the overworld. This mechanic is entirely custom and fights the static grid nature of the engine.

## Future Investigation Strategy (Reference `usdasm`)
1.  **Vanilla Transitions:** Study `Bank02.asm` in `usdasm` to see how `Module09_Overworld` handles coordinate handoffs.
    -   Look for `Overworld_ScrollMap` and `Overworld_HandleCardinalCollision`.
2.  **Camera Re-centering:** Search for routines that "center" the camera on Link after a transition (`Overworld_SetCameraBoundaries`). We may need to manually invoke this *after* the transition logic finishes, rather than snapping coordinates *before*.
3.  **Scroll Register Reset:** Instead of zeroing `$E1` etc., we might need to recalculate them based on the *new* area's properties immediately upon load.

## Workaround
The bug is non-fatal. Players can navigate out of the area, though the visual transition may be jarring.

## Related Files
-   `Overworld/lost_woods.asm`
-   `Overworld/ZSCustomOverworld.asm`
-   `usdasm/bank_02.asm` (Reference)
