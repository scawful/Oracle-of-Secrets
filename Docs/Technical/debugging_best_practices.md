# Oracle of Secrets - Debugging Best Practices

**Created:** 2026-01-23
**Purpose:** Prevent regressions and bugs based on lessons learned

---

## Pre-Implementation Checklist

Before implementing changes to sprite behavior or overworld systems:

### 1. Verify Vanilla Behavior
- [ ] Read vanilla disassembly (`jpdasm` or `usdasm`) for the routine you're using
- [ ] Confirm which RAM addresses the routine reads/writes
- [ ] Check if the sprite slot/RAM address is repurposed in Oracle's custom code
- [ ] Document assumptions explicitly in code comments

### 2. Identify Impact Scope
- [ ] List ALL call sites of modified routines
- [ ] Check if ZSCustomOverworld has hooks that might conflict
- [ ] Verify which timers/state variables the sprite already uses

### 3. Document Before Coding
- [ ] Add TODO comments explaining intent
- [ ] Note vanilla behavior vs custom behavior differences

---

## Testing Protocol

### Overworld Transitions
After ANY change to overworld or coordinate code:

1. **Area Type Matrix** - Test transitions between ALL combinations:
   - small (1x1) ↔ small
   - small ↔ large (2x2)
   - small ↔ tall (1x2)
   - small ↔ wide (2x1)
   - large ↔ tall
   - large ↔ wide
   - tall ↔ wide

2. **Lost Woods Specific**
   - Valid combo completion (N, W, S, W → exit East)
   - Invalid combo then exit (any wrong direction → return)
   - Multiple invalid attempts → exit
   - Camera alignment after each transition

3. **Use Mesen2 Debugging**
   - Watch RAM addresses during transition: `$20-$23`, `$E1-$E9`
   - Use sprite viewer to verify probe spawning/despawning
   - Set breakpoints on `OverworldHandleTransitions`

### Sprite Systems
After changes to sprite detection/AI:

1. Test with walls/obstacles between sprite and Link
2. Test at various distances (near, medium, detection threshold, far)
3. Verify probe sprites spawn and despawn correctly
4. Check sprite slot count doesn't overflow from probe spawning

---

## Critical RAM Address Reference

### Sprite Addresses (indexed by X)
| Address | Name | Notes |
|---------|------|-------|
| `$0D80,X` | SprState | **Set by vanilla probe on Link contact** |
| `$0DB0,X` | ProbeParent | Stores (parent_slot + 1) |
| `$0DD0,X` | SprType | Sprite type/ID |
| `$0EE0,X` | SprTimerD | General timer - **NOT probe-specific** |
| `$0E00,X` | SprTimerA | Cooldown timer |
| `$0E10,X` | SprTimerB | Alt cooldown timer |
| `$0DF0,X` | SprAction | State machine index |

### Link/Overworld Addresses
| Address | Purpose |
|---------|---------|
| `$20-$21` | Link Y position (16-bit) |
| `$22-$23` | Link X position (16-bit) |
| `$8A` | Current area ID |
| `$E1`, `$E3` | X scroll registers |
| `$E7`, `$E9` | Y scroll registers |

---

## Regression Response Protocol

### Severity Assessment

**Major Regression** (revert immediately):
- Wrong map loaded on transition
- Camera completely misaligned (> 1 tile off)
- Soft lock or crash
- Link teleported to wrong coordinates

**Minor Bug** (document and defer):
- Slight camera offset (< 1 tile)
- Minor visual glitch
- Non-fatal playability issue

### Response Steps

1. **Major:** Revert changes immediately, document what broke
2. **Minor:** Keep stable version, create issue doc in `Docs/Issues/`
3. **Always:** Add NOTE comment explaining disabled code

### Comment Template for Disabled Code
```asm
; NOTE: [Feature] was causing [problem description]
; The [specific mechanism] interfered with [other system].
; Disabled pending investigation. See Docs/Issues/[issue_file].md
; JSL DisabledRoutine
```

---

## Known Conflicts

### LostWoodsPuzzle ↔ ZSCustomOverworld
**Conflict:** Coordinate manipulation timing

**Problem:** `LostWoods_ResetCoordinates` snapped coordinates DURING transition flow, but `OverworldHandleTransitions` uses current position for destination calculation.

**Correct Approach:**
- Track accumulated coordinate drift during puzzle
- Apply inverse correction AFTER transition completes
- Or: Recalculate scroll registers post-load based on new area properties

### VanillaProbeSystem Assumptions
**Common Mistake:** Assuming probe sets `SprTimerD`

**Reality:** Vanilla probe sets parent's STATE (`$0D80,X`), not timers

**Correct Usage:**
```asm
; Check if probe detected Link
LDA.w SprState, X : CMP.b #$XX : BEQ .detected
```

---

## Debugging Commands (Mesen2)

```
; Watch sprite state for slot 0
watch $0D80

; Watch Link's position
watch $20 w  ; Y position (16-bit)
watch $22 w  ; X position (16-bit)

; Watch scroll registers
watch $E1
watch $E7

; Breakpoint on area transition
bp $02A5EC  ; Overworld_ActualScreenID
```

---

## File Reference

| System | Primary File | Notes |
|--------|-------------|-------|
| Sprite helpers | `Core/sprite_functions.asm` | Probe routines, common utilities |
| Overworld transitions | `Overworld/ZSCustomOverworld.asm` | Area type handling |
| Lost Woods | `Overworld/lost_woods.asm` | Puzzle logic, coordinate manipulation |
| Enemy sprites | `Sprites/Enemies/*.asm` | Individual sprite AI |
| Vanilla reference | `../alttp-gigaleak/DISASM/jpdasm/` | JP disassembly |
| US reference | `../alttp-gigaleak/DISASM/usdasm/` | US disassembly (if generated) |
