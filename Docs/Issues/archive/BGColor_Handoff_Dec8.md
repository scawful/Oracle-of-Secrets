# BGColor Regression Handoff - December 8, 2025

## Problem Summary

Custom area BG colors appear **TOO BRIGHT** during walking transitions on the overworld. The color is being ADDED to, not failing to darken.

**Expected**: `$2669` (#489848) - the value in ZScream's Pool_BGColorTable
**Actual**: `#7CCC7E` - approximately +6 brightness per 5-bit RGB channel

This is **color ADDITION**, not missing subtraction. The SNES hardware is adding fixed color to the screen.

---

## Key Technical Details

### SNES Color Math Registers
| Register | Shadow | Purpose |
|----------|--------|---------|
| $2130 (CGSWSEL) | $99 | Color math window/mode selection |
| $2131 (CGADDSUB) | $96 | Which layers participate, add vs subtract |
| $2132 (COLDATA) | $9C/$9D/$9E | Fixed color values (R/G/B intensity) |

### Subscreen Enable
- `$1D` controls subscreen overlay enable
- When `$1D = 1`, BG1 is on subscreen and color math can apply
- When `$1D = 0`, no subscreen overlay

### Fixed Color Format (COLDATA)
- Bits 0-4: Intensity (0-31)
- Bit 5: Blue channel select
- Bit 6: Green channel select
- Bit 7: Red channel select

Neutral values (intensity 0): `$9C=$20, $9D=$40, $9E=$80`
Death Mountain values: `$9C=$26 (+6 blue), $9D=$4C (+12 green), $9E=$8C (+12 red)`

---

## What We Know

1. **The symptom is uniform +6 brightness** - all RGB channels brightened equally
2. **Song of Storms (rain) temporarily fixes it** - because it forces a complete palette refresh
3. **Walking transitions trigger it** - not bird travel, not time turnover
4. **Both mosaic AND non-mosaic transitions** show the bug

---

## Hypothesis: $1D Not Being Cleared

### Evidence
1. **NOP at $0BFE70**: Vanilla `Overworld_SetFixedColAndScroll` starts with `STZ.b $1D`. Oracle NOPs this out to prevent visual flash during warps.

2. **Song of Storms fix removed STZ.b $1D**: Commit `841ef2d` removed initial `STZ.b $1D` from `ActivateSubScreen` to preserve rain across transitions.

3. **Time system calls the NOPed function**: `TimeSystem_UpdatePalettes` (time_system.asm:189) calls `Overworld_SetFixedColAndScroll` expecting it to clear $1D, but it doesn't anymore.

### Theory
If player visits an area with overlay (rain, fog, canopy) → $1D = 1
Then walks to normal area → $1D should be cleared but isn't
Result: SNES color math keeps adding fixed colors to screen

---

## Fix Attempted (DID NOT WORK)

Added to `Oracle_CgramAuxToMain_Impl` in `mask_routines.asm`:

```asm
; Fix for color addition bug: Clear $1D if no overlay active
LDA.b $8C : CMP.b #$FF : BNE .has_overlay
  LDA.l $7EE00E : BNE .has_overlay  ; Check Song of Storms
  STZ.b $1D
.has_overlay
```

This did NOT fix the issue - suggests the problem may be elsewhere.

---

## Alternative Theories to Investigate

### 1. Fixed Color Values Persisting
The uniform +6 doesn't match Death Mountain values (+6/+12/+12). Where does uniform +6 come from?
- Check what values are actually in $9C/$9D/$9E during the bug
- Use emulator debugger to watch these registers

### 2. Color Math Mode ($96) Enabled
Even if $1D is cleared, if $96 (CGADDSUB) has bits set for the relevant layers, color math could still apply.
- Check if $96 is being set somewhere and not cleared
- Line 2120 in ZSCustomOverworld.asm zeros $96, but only during spotlight transitions

### 3. Different Code Path
Walking transitions may go through a completely different code path that:
- Sets non-zero fixed colors
- Enables color math
- Never clears either

### 4. NMI Timing Issue
The correct values might be written but overwritten by NMI before they take effect.

---

## Key Files

| File | Relevance |
|------|-----------|
| `Overworld/ZSCustomOverworld.asm` | NOP at $0BFE70, overlay handling, fixed color writes |
| `Overworld/time_system.asm` | ColorSubEffect, BackgroundFix, TimeSystem_UpdatePalettes |
| `Masks/mask_routines.asm` | Oracle_CgramAuxToMain_Impl hook at $02C769 |

---

## Key Addresses

| Address | Function | Notes |
|---------|----------|-------|
| $0BFE70 | Overworld_SetFixedColAndScroll | NOPed STZ.b $1D |
| $0BFE72 | Alt entry (skips STZ.b $1D) | Used when preserving overlay |
| $0BFEB6 | Overworld_LoadBGColorAndSubscreenOverlay | Sets $1D=1 for overlays |
| $02C769 | Overworld_CopyPalettesToCache | Hooked by Oracle_CgramAuxToMain_Impl |
| $288000 | Pool_BGColorTable | ZScream custom BG colors |

---

## Debugging Approach

1. **Set breakpoints** on $9C/$9D/$9E writes to find what's setting non-zero intensity
2. **Watch $1D** during walking transition to see if/when it's set to 1
3. **Watch $96** to see if color math is being enabled
4. **Compare** working scenario (after Song of Storms) vs broken scenario

---

## Commits in This Branch

| Commit | Description | Status |
|--------|-------------|--------|
| `841ef2d` | Song of Storms fix - removed STZ.b $1D | Suspect |
| `d01a4b8` | ActivateSubScreen fall-through fix | Related |
| `2b504d9` | Time System BG color tinting | Was thought to be "known good" |

---

## Questions to Answer

1. What exact value is in $9C/$9D/$9E when the bug occurs?
2. What value is $96 (CGADDSUB) during the bug?
3. What value is $1D during the bug?
4. Is the bug present immediately on game start, or only after visiting certain areas?
5. What code path sets the problematic values?
