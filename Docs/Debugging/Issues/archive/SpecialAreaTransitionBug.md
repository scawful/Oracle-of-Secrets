# Issue: Special Overworld Transition Color Glitch & Time Sync

## Status: Partially Resolved (Stable but Visual Glitch Remains)

## Description
When transitioning between Overworld areas, specifically involving Special Overworlds or just standard scrolling, the background color logic has historically been unstable.
-   **Previous Issues:** "Weird Purple" flash (Fixed via math clamp), Game Crash on transition (Fixed via hook repair).
-   **Current Issue:** When transitioning, the background color loads the **Base Color** defined in ZSCustomOverworld (e.g., standard green) but **fails to apply the Time System Tint** (e.g., Night/Sunset) until the transition completes. This results in a jarring "Flash to Day" effect during the scroll if it is currently Night.

## Technical History & Fixes

### 1. The "Purple Flash" (Fixed)
-   **Cause:** `ColorSubEffect` in `time_system.asm` was subtracting values from a dark base color (like black in Special Areas). This caused an integer underflow (wrapping around to `$FFFF` or similar high values), resulting in a purple/grey artifact.
-   **Fix:** Updated `Overworld/time_system.asm` to clamp subtraction results to `#$0000` (Black).

### 2. The Crash (Fixed)
-   **Cause:** A hook in `ZSCustomOverworld.asm` at `$0BFE70` (`Overworld_SetFixedColorAndScroll_Interupt`) used `JML $0BFE76`. This target address was in the middle of a vanilla 3-byte instruction (`LDX #$19C6`), causing the CPU to execute garbage bytes (`FE ...`) and crash.
-   **Fix:** Implemented a safe handler wrapper `Overworld_SetFixedColorAndScroll_Handler` that restores the overwritten instructions (`STZ $1D`, `REP #$30`, `LDX #$19C6`) correctly before jumping back to a valid instruction boundary.

## Outstanding Issue: Missing Time Tint During Transition

The game remains stable, but the visual continuity is broken.

### Symptoms
1.  Player is in Overworld at Night (Blue tint).
2.  Player moves to edge of screen to transition.
3.  As the scroll begins, the background color instantly reverts to "Base Green" (Daytime).
4.  Scroll completes.
5.  Time System logic kicks in again, snapping the color back to Night Blue.

### Root Cause Analysis
The `ReplaceBGColor` function in `ZSCustomOverworld.asm` is responsible for loading the base color and *attempting* to tint it.
It calls `JSL Oracle_BackgroundFix` (which links to `BackgroundFix` -> `ColorSubEffect` in `time_system.asm`).

However, during the transition loop (NMI / Scroll Module), the updates to the palette buffer (`$7EC540`) might be:
1.  **Overwritten** by a vanilla routine later in the frame.
2.  **Ignored** because the Time System's `CheckCanRun` routine returns false during the transition state (`$11 != $09`), preventing the tint from being calculated or applied.

### Investigation Strategy for Next Agent
1.  **Check `TimeSystem_CheckCanRun`**: In `Overworld/time_system.asm`, verify if the routine allows execution during Module `$09` (Overworld) but *specifically* checks Submodule `$11`. If `$11` is set to `$23` (Scrolling/Mosaic), does it exit early?
    *   *Hypothesis:* The Time System deliberately pauses during transitions to avoid glitches, but this pause prevents the destination color from being tinted before it is displayed.
2.  **Trace `ReplaceBGColor`**: Verify that when `Overworld_SetFixedColorAndScroll_Handler` calls `ReplaceBGColor`, the `Oracle_BackgroundFix` is actually executing and writing a tinted value to the buffer.
3.  **Force Tint on Load**: You may need to explicitly run the `ColorSubEffect` logic *once* manually on the destination color immediately before the scroll starts, rather than relying on the per-frame Time System loop.

### Relevant Files
-   `Overworld/ZSCustomOverworld.asm`: Look at `Overworld_SetFixedColorAndScroll_Handler` and `ReplaceBGColor`.
-   `Overworld/time_system.asm`: Look at `TimeSystem_CheckCanRun` and `BackgroundFix`.