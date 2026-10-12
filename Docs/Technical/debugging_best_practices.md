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

## Agent Preflight (Before Live Debugging)

Requires the sibling mesen2-oos checkout or `MESEN2_OOS_ROOT` (`Scripts/Mesen2/mesen2_client.py`).

1. **Confirm emulator run state**
   - `python3 Scripts/Mesen2/mesen2_client.py run-state`
   - If paused, resume or use `--allow-paused` for intentional step testing.
2. **Capture baseline diagnostics**
   - `python3 Scripts/Mesen2/mesen2_client.py diagnostics --json`
   - Deep capture (items/flags/sprites/watch): `python3 Scripts/Mesen2/mesen2_client.py diagnostics --deep --json`
   - Note mode/submode, time phase, and camera offsets.
3. **Create a labeled save state at the exact repro point**
   - `python3 Scripts/Mesen2/mesen2_client.py save 1` (slots 1-99 or configured)
   - `python3 Scripts/Mesen2/mesen2_client.py savestate-label set 1 --label "Dark World south crash"`
   - `python3 Scripts/Mesen2/mesen2_client.py lib-save "Dark World south crash"`
4. **Log actions explicitly**
   - Record whether inputs are agent-driven or user-driven in scratchpad.

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
   - Run `python3 Scripts/Debug/repro_blackout_transition.py` for black-screen detection on a transition

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
| `$0D80,X` | SprAction | State machine index. **Vanilla probe writes 3 here on Link contact** |
| `$0DB0,X` | SprMiscB | Prober parent sprite ID (parent_slot + 1) |
| `$0DD0,X` | SprState | Sprite state |
| `$0E20,X` | SprType | Sprite type/ID |
| `$0DF0,X` | SprTimerA | Action timer. Vanilla probe sets $10 |
| `$0E00,X` | SprTimerB | Animation timer |
| `$0E10,X` | SprTimerC | Timer |
| `$0EE0,X` | SprTimerD | General timer - **NOT set by probe** |

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
2. **Minor:** Keep stable version, create issue doc in an issue note under the AFS scratchpad (~/.context/projects/oracle-of-secrets/scratchpad/, AGENTS.md rule 5)
3. **Always:** Add NOTE comment explaining disabled code

### Comment Template for Disabled Code
```asm
; NOTE: [Feature] was causing [problem description]
; The [specific mechanism] interfered with [other system].
; Disabled pending investigation. See the issue note [issue_file].md in the AFS scratchpad (~/.context/projects/oracle-of-secrets/scratchpad/).
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

**Reality (per usdasm bank_05.asm:12080-12104; static reading, runtime unverified):** the vanilla probe sets the parent's SprAction (`$0D80,X`) = 3 and SprTimerA (`$0DF0,X`) = $10, unless the parent's SprAction is already 3 or its type (`$0E20,X`) is $CE.

**Correct Usage:**
```asm
; Check if probe detected Link. Valid only for sprites whose action 3 means alerted;
; otherwise the probe hijacks their state machine.
LDA.w SprAction, X : CMP.b #$03 : BEQ .detected
```

---

## Debugging Commands (Mesen2)

```
; Watch sprite state for slot 0
watch $0D80 ; SprAction, slot 0

; Watch Link's position
watch $20 w  ; Y position (16-bit)
watch $22 w  ; X position (16-bit)

; Watch scroll registers
watch $E1
watch $E7

; Breakpoint on area transition
bp $02A5EC  ; Overworld_ActualScreenID

; Run-state / diagnostics
python3 Scripts/Mesen2/mesen2_client.py run-state
python3 Scripts/Mesen2/mesen2_client.py time
python3 Scripts/Mesen2/mesen2_client.py diagnostics --json
python3 Scripts/Mesen2/mesen2_client.py savestate-label set 1 --label "Dark World south crash"
python3 Scripts/Mesen2/mesen2_client.py lib-save "Dark World south crash"
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
