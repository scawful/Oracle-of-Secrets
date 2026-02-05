# HUD Artifact Bug - RESOLVED

## Problem Description
A brown/black tile artifact appeared below the item box in the HUD after closing the menu on the overworld.

## Resolution
**Status: FIXED** (commit `1c19788`)

The bug was caused by the `FloorIndicator` function in `Menu/menu_hud.asm` exceeding its allocated 156-byte size limit. This was introduced in commit `841ef2d` ("Fix Song of Storms") which added floor indicator logic that pushed the function over its size boundary.

The fix reverted the `FloorIndicator` function to stay within its vanilla size constraint at `$0AFD0C-$0AFDA7`.

---

## Technical Details

### Root Cause
The ALTTP ROM has a specific memory layout where `FloorIndicator` must fit within 156 bytes (`$0AFD0C-$0AFDA7`). When the function exceeded this limit, it overwrote adjacent data/code, causing the HUD tile corruption.

### Key Commit
- `1c19788` - "Fix HUD artifact: Revert FloorIndicator overflow from Song of Storms commit"

### Files Affected
- `Menu/menu_hud.asm` - FloorIndicator function

---

## Historical Investigation

Before the root cause was identified, several other hypotheses were investigated:

1. **ActivateSubScreen $1D handling** - Not the cause
2. **Menu cursor tile cleanup** - Not the cause
3. **Palette restoration** - Not the cause

The breakthrough came from checking function size constraints against vanilla ROM layout.
