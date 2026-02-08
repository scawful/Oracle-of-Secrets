# Sprite ID Overflow Resolution

**Date:** 2026-01-31
**Status:** RESOLVED
**Symptoms:** Slot 1 overworld black screen, Slot 2 dungeon entry freeze
**Root cause:** WindmillGuy sprite ID `$F8` exceeds vanilla table capacity (`$F2` max)

## Problem

Vanilla ALTTP has 8 property byte-tables in bank `$0D`, each sized for exactly 243 entries (`$00`-`$F2`). The tables are packed sequentially with `$F3` bytes per table. The last table (Table 8: deflect/impervious flags) ends at `$0DB817`, immediately before `SpritePrep_LoadProperties` code at `$0DB818`.

WindmillGuy was assigned sprite ID `$F8`, which is 6 entries past the table boundary. The `Set_Sprite_Properties` macro writes to `$0DB725 + $F8 = $0DB81D` — 5 bytes into the `SpritePrep_LoadProperties` routine. This corrupted the vanilla code at ROM build time.

### Corruption chain

1. Assembler writes WindmillGuy's Table 8 property byte (`$46`) to `$0DB81D`
2. `SpritePrep_LoadProperties` (called for ALL sprite init) reads corrupted code
3. CPU jumps to `$83:A607` (unallocated data region in bank `$03`)
4. Executes ~4000 bytes of data as instructions, hits a TCS-equivalent
5. SP set to `$0D0C` (outside `$01xx` stack page)
6. NMI saves/loads corrupted SP from `$7E1F0A` via TCS -> permanent black screen

### Why it was hard to find

- **Assembly-time corruption**: The bug existed in the ROM binary, not as a runtime race condition. No breakpoints, memory watches, or SP polling could catch the "moment" of corruption.
- **Intermittent appearance**: Slot 1 (overworld) only crashed when sprites were initialized. Slot 2 (dungeon entry) crashed more reliably due to bulk sprite prep on room load.
- **Indirect symptoms**: The corrupted routine is called for every sprite, making crashes appear to originate from whichever sprite happened to spawn.

## Fix

### 1. Reassign WindmillGuy ID: `$F8` -> `$B2`

`$B2` is within the valid `$00`-`$F2` range. It was vanilla's "Pipe Right" sprite (unused in final ALTTP) and confirmed free in both the Oracle sprite CSV and codebase.

**File:** `Sprites/all_sprites.asm:37`

### 2. Dispatch bounds guards

Added to both `NewSprTable` and `NewSprPrepTable` in `Core/sprite_new_table.asm`:
- **Bounds check:** `CMP #$00F3 : BCS .null_sprite` rejects IDs > `$F2`
- **Null pointer guard:** `ORA $06 : ORA $07 : BEQ .null_sprite` catches unregistered sprite entries (`$000000`) that would otherwise `JMP [$0006]` through scratchpad RAM

## Valid sprite ID range

The maximum valid sprite ID is **`$F2`** (243 entries, `$00`-`$F2`). Any sprite assigned an ID > `$F2` will overflow all 8 vanilla property tables in bank `$0D` and the 2 vanilla pointer tables in bank `$06`.

## Prevention: Sprite ID Bounds Guards

Two static analysis layers now prevent this class of bug:

### Assembler assertion (`Core/sprite_macros.asm`)
```asm
assert !SPRID <= $F2, "Sprite ID !SPRID exceeds vanilla table limit ($F2 max)."
```
Build fails instantly if any sprite file sets `!SPRID` above `$F2`. Zero runtime cost.

### z3dk ROM validation (`oracle_analyzer.py --check-sprite-tables`)
Scans the built ROM binary for:
- **Sentinel check:** Verifies `SpritePrep_LoadProperties` at `$0DB818` hasn't been overwritten (Table 8 overflow)
- **Inter-table gap scan:** Checks bytes in the `$F3`-`$FF` range of each table for non-zero values
- **Pointer table check:** Validates `$069283` (Main) and `$06865B` (Prep) have no entries past `$F2`

Both checks run automatically during `build_rom.sh`.

## Related fixes (same investigation)

- **Menu_Exit SEP #$20** (`Menu/menu.asm`): Restored M=8 before RTS to prevent width leak
- **ColorBgFix REP #$20** (`Overworld/time_system.asm`): Defensive width-match for PHA/PLA balance
- **Wolfos label cleanup** (`Sprites/Bosses/wolfos.asm`): Replaced hardcoded `$7EF303` with `InCutSceneFlag` label
