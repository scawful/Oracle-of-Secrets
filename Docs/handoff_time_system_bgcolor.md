# Handoff: Time System Custom BG Color Tinting Bug

## Problem Statement

When the time system advances the hour in areas with overlays (e.g., Lost Woods with canopy overlay `$9E`), the **custom background color turns bright green (untinted)** instead of being darkened by the time-of-day tinting system.

The time system should apply a color subtraction effect to all palettes, including the custom BG color, based on the current hour. This works correctly for sprites and most BG tiles, but the custom BG color (at palette position 0) remains at its original bright value.

## Symptoms

1. Enter Lost Woods (or any area with custom BG color + overlay)
2. Wait for the hour to advance (or use Song of Time)
3. **Expected**: BG color darkens with time of day
4. **Actual**: BG color becomes bright/untinted green

Additionally, some attempted fixes caused the **overlay to disappear entirely** (controlled by `$1D` register).

## Architecture Overview

### Palette Buffer System

| Buffer | Address | Purpose |
|--------|---------|---------|
| Staging HUD | `$7EC300` | Source palette data |
| Staging BG | `$7EC340` | Source palette data |
| Staging Sprite | `$7EC400` | Source palette data |
| Effective HUD | `$7EC500` | What gets DMA'd to CGRAM |
| Effective BG | `$7EC540` | What gets DMA'd to CGRAM |
| Effective Sprite | `$7EC600` | What gets DMA'd to CGRAM |

The BG color is stored at **position 0** of these buffers (`$7EC500`, `$7EC540`, etc.).

### Key Variables

| Variable | Address | Purpose |
|----------|---------|---------|
| `Hours` | `$7EE000` | Current hour (0-23) |
| `!SubPalColor` | `$7EE018` | Temp storage for ColorSubEffect input |
| `$8C` | WRAM | Current overlay type ($9E = canopy, $9F = rain, etc.) |
| `$1D` | WRAM | Subscreen/overlay enable flag |

### Key Routines

1. **`RunClock`** (`time_system.asm:99`) - Increments time, triggers palette updates
2. **`ColorSubEffect`** (`time_system.asm:382`) - Applies RGB subtraction based on hour
3. **`BackgroundFix`** (`time_system.asm:448`) - Wrapper that calls ColorSubEffect for BG color
4. **`ReplaceBGColor`** (`ZSCustomOverworld.asm:3816`) - ZS hook that loads custom BG color
5. **`InitColorLoad2`** (`ZSCustomOverworld.asm:3941`) - Another path that sets BG color
6. **`Overworld_SetFixedColAndScroll`** (`$0BFE70`) - Vanilla routine for BG color setup

## Code Flow When Hour Advances

```
RunClock
  |
  v
.increase_hours
  |
  v
JSL RomToPaletteBuffer     ; Reload palettes from ROM
JSL PaletteBufferToEffective ; Copy staging -> effective (with tint hooks)
  |
  v
Check overlay ($8C)
  |-- $9E (canopy) --> JSL Overworld_SetFixedColAndScroll_AltEntry
  |-- $9F (rain) ----> JSL Overworld_SetFixedColAndScroll_AltEntry
  |-- other ---------> JSL Overworld_SetFixedColAndScroll
  |
  v
ZS Hook at $0BFEB6 intercepts
  |
  v
Overworld_LoadBGColorAndSubscreenOverlay
  |
  v
JSL ReplaceBGColor
  |-- Loads color from Pool_BGColorTable
  |-- Stores to $7EE018
  |-- JSL Oracle_BackgroundFix
  |     |-- Should apply ColorSubEffect
  |     |-- Write to $7EC500, $7EC300, $7EC540, $7EC340
  v
Continue with overlay setup
```

## Root Causes Identified by Agent Swarm

### 1. Untinted Color Overwrite in InitColorLoad2
The `InitColorLoad2` routine in `Overworld/ZSCustomOverworld.asm` (hooked at `$0ED627` for screen transitions) was loading the raw background color from the `Pool_BGColorTable` and writing it directly to the palette buffers, bypassing the time-of-day tinting logic. This caused the color to revert to its base value whenever a screen loaded.

### 2. Addressing Mode Error in ColorSubEffect
The `ColorSubEffect` routine in `Overworld/time_system.asm` was accessing global RAM variables (`$7EE016`, `$7EE018`) using short addressing modes (e.g., `CMP !TempPalColor`) without ensuring the Data Bank Register (DB) was set to `$7E`. This caused it to read garbage data when called from `ZSCustomOverworld.asm` (where DB is typically not `$7E`), resulting in incorrect or failing tint calculations.

### 3. Overlay Clearing Logic
The `Overworld_LoadBGColorAndSubscreenOverlay` routine (which hooks the screen update logic) had two flaws that caused it to disable valid overlays when the hour changed:
1.  **Static vs. Dynamic**: It was reading the overlay ID from a static table (`ReadOverlayArray`) instead of the active runtime variable (`$8C`). This meant dynamic overlays (like Rain toggled by an item) were ignored.
2.  **Incomplete Logic**: The routine only explicitly handled a subset of overlay IDs (`$9F`, `$9D`, `$96`, `$95`, `$9C`). Any valid overlay *not* in this list (such as Canopy `$9E`, Fog `$97`, or Bridge `$94`) would fall through to a "disable" block that executed `STZ $1D`, turning off the overlay layer.

## Fixes Applied

### 1. Fixed Addressing in `time_system.asm`
Added `.l` (long) suffixes to all variable accesses in `ColorSubEffect` (e.g., `LDA.l !SubPalColor`, `CMP.l !TempPalColor`) to ensure correct memory access regardless of the current Data Bank.

### 2. Integrated Tinting in `ZSCustomOverworld.asm`
Updated `InitColorLoad2` to call `Oracle_BackgroundFix` (which wraps `ColorSubEffect`) instead of writing raw values. This ensures that the background color is properly tinted for the current time of day immediately upon screen load.

### 3. Overlay Preservation in `ZSCustomOverworld.asm`
In `Overworld_LoadBGColorAndSubscreenOverlay`:
1.  **Dynamic ID Check**: Replaced the static table lookup with `LDA.b $8C` to ensure the *currently active* overlay is evaluated.
2.  **Fallthrough Protection**: Added a safety check (`CMP.w #$00FF : BNE .noCustomFixedColor`) just before the disable block. This ensures that *any* valid overlay ID (anything that isn't `$00FF`) will bypass the disable instruction and instead proceed to enable the subscreen with default fixed colors.

## Verification Results

-   **Time Tinting**: The background color now correctly darkens as time passes and persists across screen transitions.
-   **Overlay Persistence**: Overlays (Canopy, Rain, Fog, etc.) are no longer cleared when the hour advances.
-   **Overlay Stability**: `$1D` register is correctly managed, preventing "disappearing overlay" regressions.

## Files Involved

- `Overworld/time_system.asm` - Time system and tinting routines
- `Overworld/ZSCustomOverworld.asm` - Custom BG color system, hooks

## Test Case

1. Start game, enter Lost Woods
2. Set time to evening (hour 18+) using debug or Song of Time
3. Observe: BG color should be darkened
4. Wait for hour to advance
5. Observe: BG color should remain darkened AND overlay (canopy) should remain visible.