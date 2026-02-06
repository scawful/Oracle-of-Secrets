# Dream Sequence Implementation Plan

**Salvaged from:** `feature/dream-sequences` worktree (2025-12-09)
**Status:** Early prototype — hooks written, no dream content yet

## Overview

Implement 6 dream sequences for story progression using existing `attract_scenes.asm` infrastructure.

## Prototype Code (from worktree)

Two hooks were prototyped to force "dream state" by overriding bunny transformation:

### Hook 1: BunnyTransformation Override ($07:82DA)
Intercepts `LDA $03F5 / ORA $03F6` check. When `!DREAM_STATE_ACTIVE` ($7EF411) is set, clears Zero flag so BEQ fails, forcing bunny logic path.

### Hook 2: Moon Pearl Check Override ($07:83D0)
When dream state active, returns 0 for moon pearl check to force bunny transformation.

### Macros
- `%SetDreamState(active)` — PHP/SEP/STA/PLP safe setter
- `%BranchIfDreamActive(label)` — LDA.l + BNE
- `%BranchIfDreamInactive(label)` — LDA.l + BEQ

## Technical Approach

### Infrastructure (Already Exists)
- **Base System:** `attract_scenes.asm` provides scene infrastructure
- **SRAM Tracking:** Dreams bitfield at `$7EF410`
- **Triggering:** GameState checks + OOSPROG flags

### Data Structure
```asm
DreamSequences:
  .dream1: dw Dream1_Init, Dream1_Main, Dream1_Cleanup
  .dream2: dw Dream2_Init, Dream2_Main, Dream2_Cleanup
  ; ... 4 more
```

### Per-Dream Pattern
Each dream needs:
- Init: Load GFX, palette, tilemap
- Main: Scene animation, dialogue boxes
- Cleanup: Restore game state
- Flag update: Mark as seen in `$7EF410`

### Integration Points
- Sleep trigger (bed interaction)
- Story progression points
- Event completion callbacks

## Files to Create/Modify

**New Files:**
- `Core/dream_sequences.asm` — Dream scene implementations
- `Core/dream_triggers.asm` — Trigger logic

**Modified Files:**
- `oracle.asm` — Include new files
- `Core/sleep_handler.asm` — Add dream trigger call

## Success Criteria

- [ ] All 6 dreams implemented and tested
- [ ] SRAM tracking verified (flags persist)
- [ ] Trigger conditions work correctly
- [ ] No memory conflicts
- [ ] Documented
