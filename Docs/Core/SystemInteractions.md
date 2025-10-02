# System Interaction & Compatibility Analysis

References:
- `Docs/ZSCustomOverworld.md`
- `Docs/TimeSystem.md`

## 1. Overview

This document details the analysis of interactions between `ZSCustomOverworld` and other advanced systems in Oracle of Secrets. It outlines potential conflicts and proposes solutions to ensure they work together correctly.

## 2. ZSCustomOverworld vs. Time System

- **System:** `Overworld/time_system.asm`
- **Interaction Point:** Palette Modulation.

### Analysis

Both systems modify overworld palettes. ZSCustomOverworld sets the **base palette** for each area from its tables. The Time System applies a **color transformation** on top of the existing palette to simulate lighting changes.

The conflict arises if the Time System reads the palette *before* ZSCustomOverworld has loaded the area-specific one, or if one system's writes completely overwrite the other's.

The key routine is `LoadDayNightPaletteEffect` in `time_system.asm`, which is hooked into the game's main palette-loading functions. It intercepts every color write to CGRAM, applies its color subtraction logic, and then writes the final value.

### Conclusion & Solution

The current implementation is **mostly compatible by design**. The Time System's `LoadDayNightPaletteEffect` acts as a filter on all palette writes. When ZSCustomOverworld writes a new base palette to CGRAM, the Time System intercepts these writes and applies the day/night effect.

**Recommendations:**
1.  **No Code Change Needed for Compatibility (at this time):** The current hook-based approach should work. ZSCustomOverworld loads the base palette, and the Time System modifies it on the fly.
2.  **Move Patches:** The `org` patches in `time_system.asm` should be moved to `Core/patches.asm` for consistency. This is a code organization improvement, not a compatibility fix.

## 3. ZSCustomOverworld vs. Lost Woods Puzzle

- **System:** `Overworld/lost_woods.asm`
- **Interaction Point:** Overworld Screen Transitions.

### Analysis

The Lost Woods puzzle works by intercepting the screen transition logic. When the player is in area `$29`, the `LostWoods` routine at `$A0F000` runs. It checks the player's exit direction against a predefined sequence. If the sequence is incorrect, it manually changes the player's and camera's coordinates to loop them back within the same screen, creating the maze effect.

ZSCustomOverworld heavily modifies the screen transition logic via its hook at `OverworldHandleTransitions` (`$02A9C4`). The conflict is that ZSCustomOverworld's new, more complex transition logic does not account for the Lost Woods puzzle's override.

### Conclusion & Solution

This is a **direct conflict** that requires integration. The Lost Woods logic needs to be explicitly called from within ZSCustomOverworld's transition handler.

**Recommendations:**
1.  **Modify `OverworldHandleTransitions`:** In `ZSCustomOverworld.asm`, at the point where a transition is confirmed and the new screen ID is determined, add a check:
    ```asm
    ; Inside OverworldHandleTransitions, after a valid transition is detected
    LDA.b $8A  ; Current Area ID
    CMP #$29   ; Is it the Lost Woods?
    BNE .normal_transition

    ; If it is, call the Lost Woods logic
    JSL LostWoods_PuzzleHandler
    ; The handler should return with carry set if it handled the transition
    BCS .transition_handled

.normal_transition
    ; ... existing ZS transition logic ...

.transition_handled
    ; ... code to finalize the transition after the puzzle logic runs ...
    ```
2.  **Refactor `lost_woods.asm`:** The code in `lost_woods.asm` needs to be refactored into a proper subroutine (`LostWoods_PuzzleHandler`) that can be called via `JSL`. It should be modified to return a status (e.g., using the carry flag) to indicate whether it has overridden the transition or if the final, correct exit has been found.

### Conclusion & Solution

This is a **direct conflict** that requires integration. The Lost Woods logic needs to be explicitly called from within ZSCustomOverworld's transition handler.

**Recommendations:**
1.  **Modify `OverworldHandleTransitions`:** In `ZSCustomOverworld.asm`, at the point where a transition is confirmed and the new screen ID is determined, add a check:
    ```asm
    ; Inside OverworldHandleTransitions, after a valid transition is detected
    LDA.b $8A  ; Current Area ID
    CMP #$29   ; Is it the Lost Woods?
    BNE .normal_transition

    ; If it is, call the Lost Woods logic
    JSL LostWoods_PuzzleHandler
    ; The handler should return with carry set if it handled the transition
    BCS .transition_handled

.normal_transition
    ; ... existing ZS transition logic ...

.transition_handled
    ; ... code to finalize the transition after the puzzle logic runs ...
    ```
2.  **Refactor `lost_woods.asm`:** The code in `lost_woods.asm` needs to be refactored into a proper subroutine (`LostWoods_PuzzleHandler`) that can be called via `JSL`. It should be modified to return a status (e.g., using the carry flag) to indicate whether it has overridden the transition or if the final, correct exit has been found.

## 4. ZSCustomOverworld vs. Song of Storms

- **System:** `Items/ocarina.asm`
- **Interaction Point:** Overworld Screen Overlays.

### Analysis

The Song of Storms summons rain by directly writing the rain overlay ID (`#$9F`) to the overlay register (`$8C`). ZSCustomOverworld, however, determines the overlay for each screen via its `.OverlayTable`. A conflict occurs when:
1.  The player plays the Song of Storms: The rain appears, but upon the next screen transition, ZSCustomOverworld will reload the area's default overlay, making the rain stop.
2.  The player dismisses the storm: The code simply clears the overlay register, potentially removing a default overlay (like fog or clouds) that should be present in that area.

### Conclusion & Solution

This is a **direct conflict**. The Song of Storms logic must be made aware of ZSCustomOverworld's overlay system to properly override and restore the correct overlay.

**Implemented Solution:**
1.  **New SRAM Variable:** `SRAM_StormsActive` (`$7EF39D`) has been added to `Core/sram.asm` to persistently track whether the Song of Storms is active.
2.  **Modified `OcarinaEffect_SummonStorms`:**
    -   This routine in `Items/ocarina.asm` now checks the current area's default overlay from `Pool_OverlayTable`. If the default is already rain (`#$9F`), it does nothing, preventing accidental cancellation of natural rain.
    -   Otherwise, it toggles the `SRAM_StormsActive` flag. Direct manipulation of the overlay register (`$8C`) has been removed from this routine.
3.  **New `HandleStormsOverlay` Routine:** A new routine `HandleStormsOverlay` has been added to `Overworld/time_system.asm`. This routine is called from `RunClock` every frame the player is in the overworld.
    -   If `SRAM_StormsActive` is set, it forces the rain overlay (`$8C = #$9F`).
    -   If `SRAM_StormsActive` is not set, it does nothing, allowing ZSCustomOverworld's normal overlay logic to apply the area's default overlay.

**Impact:** This solution ensures the rain state persists across transitions (dungeons, warps, screen changes) and correctly interacts with ZSCustomOverworld's overlay system without conflicts. It also prevents the Song of Storms from inadvertently canceling natural rain effects.

## 5. ZSCustomOverworld vs. Day/Night Sprites

- **System:** `Overworld/time_system.asm` and `Overworld/ZSCustomOverworld.asm`
- **Interaction Point:** Sprite Loading.

### Analysis

The original day/night sprite system relied on `CheckIfNight` and `CheckIfNight16Bit` routines to modify the game state (`$7EF3C5`) before vanilla sprite loading functions were called. This allowed different sprite sets to be loaded for day and night.

With ZSOW v3, the vanilla sprite loading hook (`Overworld_LoadSprites` at `$09C4E3`) is replaced by ZSOW's `LoadOverworldSprites_Interupt` (`$09C4C7`). The conflict arose because the old day/night logic was no longer being called at the correct point in the execution flow.

### Conclusion & Solution

This conflict is **ongoing**. An attempted solution to integrate the `CheckIfNight` logic directly into ZSOW's sprite loading routine caused a regression, resulting in a `BRK` after returning from `LoadOverworldSprites_Interupt`.

**Attempted Solution (Caused Regression):**
1.  **Modified `LoadOverworldSprites_Interupt`:** In `ZSCustomOverworld.asm`, a `JSL CheckIfNight` call was inserted at the beginning of this routine. `CheckIfNight` returns a potentially modified game state (e.g., `GameState + 1` for night) in the accumulator.
2.  **Adjusted Game State Usage:** The `LoadOverworldSprites_Interupt` routine then attempted to use this adjusted game state to look up the appropriate sprite set in ZSOW's `.Overworld_SpritePointers_state_..._New` tables.
3.  **`CheckIfNight` and `CheckIfNight16Bit`:** These routines in `Overworld/time_system.asm` were uncommented and available. `CheckIfNight16Bit` is already integrated into ZSOW's `Sprite_LoadGfxProperties_Interupt` (`$00FC67`), ensuring sprite graphics properties are also adjusted for day/night.

**Impact of Regression:** The game crashes with a `BRK` after `LoadOverworldSprites_Interupt` returns, indicating an issue with the state or stack after the `CheckIfNight` call. This solution is currently not viable. Further investigation is required to correctly integrate day/night sprite loading with ZSOW v3 without causing crashes.

