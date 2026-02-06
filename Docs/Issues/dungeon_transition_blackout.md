# Bug: Dungeon Transition Blackout / Softlock

**Reported:** 2026-02-06
**Severity:** Critical
**Symptom:** Screen goes black and game locks up when transitioning between dungeon rooms during casual exploration.
**Reproducibility:** Intermittent (likely correlated with rooms that draw torches during load).
**Status:** Fix implemented in ASM (pending runtime validation)

**Fix (implemented):**
- Do **not** execute `SEP #$30` before re-entering the vanilla torch draw loop at `$0188C9` (that loop runs in **16-bit** mode).
- Preserve `P/A/X/Y` around the injected `JSL WaterGate_CheckRoomEntry` so this hook returns with **vanilla** flags/register state (notably `Z=1` from the sentinel compare).

---

## Primary Suspect: Water Gate Room Load Hook

**Hook site:** `Dungeons/dungeons.asm` (`org $0188DF`)
**Implementation:** `Dungeons/Collision/water_collision.asm` (`Underworld_LoadRoom_ExitHook`)
**Feature flag:** `!ENABLE_WATER_GATE_HOOKS = 1` (currently ON)

This hook lives in the underworld room-load torch drawing routine. Even though the water-gate logic is room-gated, the hook itself runs on any room that reaches the torch loop.

---

## Ground Truth (Vanilla)

USDASM (`~/src/hobby/usdasm/bank_01.asm`) shows the torch loop is 16-bit and only switches to 8-bit on exit:

```asm
#_0188D6: LDX.b $BA
#_0188D8: LDA.l $7EFB40,X
#_0188DC: CMP.w #$FFFF
#_0188DF: BNE .draw_next_torch
#_0188E1: SEP #$30
#_0188E3: RTL
```

So `$0188C9` (loop head) assumes **16-bit A** and **16-bit X/Y**. `SEP #$30` happens only when the loop is done.

---

## Root Cause (High Confidence)

The hook previously executed `SEP #$30` on the `.draw_next_torch` path and then `JML $0188C9`.

That re-entered the vanilla torch loop with **M/X=8-bit**, but the loop contains 16-bit immediates like `CMP.w #$FFFF`. In 8-bit mode, the CPU consumes the wrong number of operand bytes and desynchronizes the instruction stream, which can present as a black screen + softlock/hang.

Secondary correctness issue: adding `JSL WaterGate_CheckRoomEntry` on the exit path clobbered processor flags and registers right before `RTL`. Vanilla returns immediately with `Z=1` from the sentinel compare; preserving `P/A/X/Y` keeps this hook transparent.

---

## Fix Implemented (Pending Validation)

**File:** `Dungeons/Collision/water_collision.asm`

- `.draw_next_torch`: jump back to `$0188C9` without changing M/X.
- Exit path: `SEP #$30` (vanilla), then save/restore `P/A/X/Y` around `JSL WaterGate_CheckRoomEntry`.

---

## Quick Validation

1. Rebuild with the fix and try repeated dungeon room transitions (include rooms with torches).
2. If it still reproduces, disable the water gate system to confirm correlation:

```asm
; Config/feature_flags.asm
!ENABLE_WATER_GATE_HOOKS             = 0
!ENABLE_WATER_GATE_OVERLAY_REDIRECT  = 0
```

---

## Debugging Steps (Mesen2 socket API)

- Breakpoint at `$0188DF`. On the BNE-taken path, confirm control returns to `$0188C9` with **16-bit M/X**.
- If the blackout happens, capture a state immediately (`python3 scripts/mesen2_client.py smart-save <slot>`), and record:
  - `$2100` (INIDISP)
  - `$10` (GameMode), `$11` (Submodule)
  - CPU `PC/P/SP`

---

## Related Files

| File | Role |
|------|------|
| `Dungeons/dungeons.asm` | Hook site (org $0188DF) |
| `Dungeons/Collision/water_collision.asm` | Hook implementation |
| `Config/feature_flags.asm` | `!ENABLE_WATER_GATE_HOOKS` toggle |
| `scripts/mesen2_client.py` | Mesen2 socket API client |
