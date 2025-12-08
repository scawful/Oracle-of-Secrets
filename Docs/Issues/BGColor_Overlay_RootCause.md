# BG Color / Overlay Regression — Resolved (March 2026)

## Resolution Summary
The "Too Bright" and "Flash to Day" bugs have been resolved by fixing the register management in `ZSCustomOverworld.asm`.

**The Problem:**
When transitioning from an area with an overlay (like Rain/Storms) to an area without one (Overlay ID `$FF`), the code cleared the Subscreen Enable register (`$1D`) but **failed to clear the Color Math Control register (`$9A`)**.
-   Rain sets `$9A` to `$72` (Additive Math).
-   If `$9A` remains `$72` in a normal area, the SNES PPU continues to perform additive color math using the Fixed Color registers (`$9C`/`$9D`).
-   This caused the background to appear significantly brighter (approx +6 per channel), turning the dark night tint into a "bright yellow-ish green".
-   This also caused the "Flash to Day" effect during transitions, as the additive brightness kicked in immediately.

**The Fix:**
Modified `ZSCustomOverworld.asm` in two key locations to ensure `$9A` is always cleared when no overlay is present.

1.  **Walking Transitions (`Overworld_ReloadSubscreenOverlay_Interupt`):**
    Added a check for Overlay `$FF` to explicitly clear `$9A`. This prevents the brightness glitch during scrolling.

    ```asm
    ; In Overworld_ReloadSubscreenOverlay_Interupt
    CPX.b #$FF : BNE .checkScroll
        LDA.b #$00 ; Disable Color Math
        BRA .loadOverlay
    ```

2.  **Dungeon/Warp/Bird Transitions (`Overworld_LoadBGColorAndSubscreenOverlay`):**
    Added `STZ.b $9A` to the block handling the `$FF` case. This prevents the glitch when exiting dungeons or warping.

    ```asm
    ; In Overworld_LoadBGColorAndSubscreenOverlay
    CMP.w #$00FF : BNE .noCustomFixedColor
        SEP #$30
        STZ.b $9A ; FIX: Clear color math
        ; ...
    ```

## Verification
-   **Brightness:** The background color in normal areas should now correctly reflect the Time System tint without extra brightness.
-   **Transitions:** Walking from a Rain area to a Normal area should no longer result in a brightness jump.
-   **Song of Storms:** Summoning and dismissing storms should work correctly, with the overlay and color math engaging and disengaging as expected.

## Technical Details
-   **File:** `Overworld/ZSCustomOverworld.asm`
-   **Routines:** `Overworld_LoadBGColorAndSubscreenOverlay`, `Overworld_ReloadSubscreenOverlay_Interupt`.
-   **Registers:** `$1D` (Subscreen), `$9A` (CGADDSUB Mirror), `$9C`/`$9D` (COLDATA Mirrors).

## Outstanding Issues
-   None related to BG Color Brightness.