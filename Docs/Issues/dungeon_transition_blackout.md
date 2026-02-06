# Bug: Dungeon Transition Blackout / Softlock

**Reported:** 2026-02-06
**Severity:** Critical
**Symptom:** Screen goes black and game locks up when transitioning between dungeon rooms during casual exploration.
**Reproducibility:** Intermittent — happens across multiple dungeons, not dungeon-specific.
**Status:** Fix implemented (pending runtime validation)
**Fix:** Restore 8-bit A/X/Y before returning to the vanilla torch loop (`SEP #$30` before `JML $0188C9` in `Underworld_LoadRoom_ExitHook`).

---

## Primary Suspect: Water Gate Room Load Hook

**File:** `Dungeons/dungeons.asm` (hook at line ~179)
**Related:** `Dungeons/Water/water_collision.asm` (implementation)
**Feature flag:** `!ENABLE_WATER_GATE_HOOKS = 1` (currently ON)

### What It Does

The hook at `org $0188DF` replaces vanilla code in the room load path and fires on **every dungeon room transition**, not just D4 water gate rooms. It was re-enabled in commit `71b62e2` after being disabled due to an unknown earlier regression.

### The Hook

```asm
org $0188DF
if !ENABLE_WATER_GATE_HOOKS == 1
  JML Underworld_LoadRoom_ExitHook
else
  BNE $0188C9    ; vanilla: branch to torch loop
  SEP #$30       ; vanilla: set 8-bit
endif
```

### The Implementation (water_collision.asm ~line 192)

```asm
Underworld_LoadRoom_ExitHook:
{
  REP #$30                    ; Force 16-bit A/X/Y
  LDX.b $BA
  LDA.l $7EFB40,X
  CMP.w #$FFFF
  BNE .draw_next_torch        ; <-- PROBLEM PATH

  SEP #$30
  JSL WaterGate_CheckRoomEntry
  RTL

  .draw_next_torch
  JML $0188C9                 ; Returns to vanilla torch loop
}
```

### Issue 1: Processor Flag Corruption (HIGH CONFIDENCE)

When the `BNE .draw_next_torch` branch is taken (which is the common case — most rooms are NOT water gate rooms), the code jumps to `$0188C9` with **16-bit A/X/Y** active (`REP #$30` was executed but never reversed).

The vanilla code at `$0188C9` expects **8-bit mode** (the original instruction sequence was `BNE $0188C9 : SEP #$30`, meaning the branch target assumes 8-bit was set before reaching it, or that 8-bit is the ambient state).

**Effect:** Vanilla torch/room drawing code operates with 16-bit registers, causing it to read wrong-sized values from RAM, corrupt state, and potentially leave `INIDISP ($2100)` in a state where the screen never turns back on.

### Issue 2: $BA Register Validity

The code uses `LDX.b $BA` without bounds checking. If `$BA` contains an unexpected value, `LDA.l $7EFB40,X` could read garbage from the torch table, causing the `CMP.w #$FFFF` check to misbehave.

### Issue 3: Stack/Return Path

The `.draw_next_torch` path uses `JML $0188C9` (long jump, no return). The `$FFFF` path uses `RTL`. This means the hook has two completely different return mechanisms depending on the branch. Verify that both paths leave the stack in the correct state for their respective continuations.

---

## Likely Fix

Add `SEP #$30` before the `.draw_next_torch` JML to restore 8-bit mode:

```asm
Underworld_LoadRoom_ExitHook:
{
  REP #$30
  LDX.b $BA
  LDA.l $7EFB40,X
  CMP.w #$FFFF
  BNE .draw_next_torch

  SEP #$30
  JSL WaterGate_CheckRoomEntry
  RTL

  .draw_next_torch
  SEP #$30                    ; <-- FIX: restore 8-bit before returning to vanilla
  JML $0188C9
}
```

---

## Quick Validation: Disable Water Gate Hooks

To confirm this is the cause, set `!ENABLE_WATER_GATE_HOOKS = 0` in `Config/feature_flags.asm` and rebuild. If the blackout disappears, this hook is confirmed as the root cause.

```asm
; Config/feature_flags.asm
!ENABLE_WATER_GATE_HOOKS             = 0    ; Disable to test
!ENABLE_WATER_GATE_OVERLAY_REDIRECT  = 0    ; Disable companion hook too
```

---

## Secondary Suspects (Lower Probability)

### custom_tag.asm — Removed Trailing pushpc

Commit `fdf4836` removed a trailing `pushpc` from `custom_tag.asm`. If this `pushpc` was balancing a `pullpc` elsewhere in the include chain, it could cause the assembler to emit code at wrong addresses. However, this would likely cause a build error or consistent crash, not intermittent blackout.

**Check:** Verify the pushpc/pullpc chain across `together_warp_tag.asm` → `custom_tag.asm`. The chain is:
1. `together_warp_tag.asm:15` — `pullpc` (restores from its own pushpc at line 10)
2. `together_warp_tag.asm:35` — `pushpc` (saves after WarpTag code)
3. `custom_tag.asm:19` — `pullpc` (restores from #2)
4. `custom_tag.asm:248` — `pushpc` (was here, now removed)

If there's a `pullpc` after `custom_tag.asm` in the include order, removing #4 would cause a stack underflow. Check `Oracle_main.asm` include order.

### D3 Prison Guard — Feature Gate

The guard rewrite in `custom_guard.asm` is wrapped in `if !ENABLE_D3_PRISON_SEQUENCE == 1`. Since the flag is `0`, all org directives (including the hook at `$05C263`) are excluded. **This should be safe**, but verify the `if` block properly wraps ALL org directives.

### @hook Annotations

These are assembly comments (`;` prefix) and cannot affect output. **Ruled out.**

---

## Debugging Steps

1. **Fastest test:** Disable water gate hooks, rebuild, retest dungeon transitions
2. **If still broken:** Check pushpc/pullpc balance with `grep -n 'pushpc\|pullpc' Dungeons/*.asm`
3. **If intermittent:** Use `scripts/mesen_transition_debug.lua` overlay to watch GameMode ($10), Submodule ($11), INIDISP ($2100) during the transition that locks up
4. **Breakpoint:** Set Mesen2 breakpoint at `$0188DF` (the hook address), step through to see if REP #$30 → JML path is taken without SEP #$30

---

## Related Files

| File | Role |
|------|------|
| `Dungeons/dungeons.asm` | Hook site (org $0188DF) |
| `Dungeons/Water/water_collision.asm` | Hook implementation |
| `Config/feature_flags.asm` | `!ENABLE_WATER_GATE_HOOKS` toggle |
| `Dungeons/custom_tag.asm` | Secondary suspect (pushpc removal) |
| `scripts/mesen_transition_debug.lua` | Debugging overlay |
