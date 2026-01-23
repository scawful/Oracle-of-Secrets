# Issue: Lost Woods Transition Coordinate Desync

## Status: Active / Low Priority
**Created:** March 2026
**Updated:** 2026-01-23
**Impact:** Subtle camera offset when exiting Lost Woods after invalid puzzle combination.

### Recent History (2026-01-23)

A coordinate reset function (`LostWoods_ResetCoordinates`) was added in commit 851da89 to fix this issue, but it caused **worse regressions**:
- Transitioning between large/small maps went to wrong coordinates
- Camera massively misaligned
- Lost Woods exit went to completely wrong map

The fix was disabled in `lost_woods.asm:42`. The original subtle bug is preferable to the severe regression.

**Current state:** Slight camera offset when exiting Lost Woods after invalid combo. Non-fatal, playable.

NOTE: Vanilla disassembly is external. In this workspace, JP gigaleak disassembly lives under `../alttp-gigaleak/DISASM/jpdasm/`. If you generate a US `usdasm` export for address parity, it lives under `../alttp-gigaleak/DISASM/usdasm/`. Adjust paths if your setup differs.

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

## Future Investigation Strategy (Reference `usdasm` / `jpdasm`)

### Why the Previous Fix Failed
The `LostWoods_ResetCoordinates` function snapped Link's coordinates DURING the transition flow, but ZSCustomOverworld's `OverworldHandleTransitions` uses Link's current position to calculate the destination. Snapping coordinates mid-calculation broke the math for large/small area transitions.

### Better Approaches to Try
1.  **Post-transition reset:** Reset scroll registers AFTER the transition completes, not during. Hook into the transition completion rather than the area ID lookup.
2.  **Track accumulated drift:** Instead of hard-snapping, track how much the puzzle has drifted the coordinates and apply the inverse when exiting.
3.  **Camera re-centering:** Search for `Overworld_SetCameraBoundaries` and invoke it after transition finishes.
4.  **Scroll register recalc:** Recalculate `$E1/$E3/$E7/$E9` based on the new area's properties AFTER load, not before.

### Vanilla Reference
Study `Bank02.asm` in `usdasm` (US) or `jpdasm` (JP):
-   `Overworld_ScrollMap` and `Overworld_HandleCardinalCollision`
-   How vanilla handles coordinate handoffs in `Module09_Overworld`

## Workaround
The bug is non-fatal. Players can navigate out of the area, though the visual transition may be jarring.

## Related Files
-   `Overworld/lost_woods.asm`
-   `Overworld/ZSCustomOverworld.asm`
-   `usdasm/bank_02.asm` or `jpdasm/bank_02.asm` (Reference)
