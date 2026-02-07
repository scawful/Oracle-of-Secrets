# Bug: Dungeon Transition Blackout / Softlock

**Reported:** 2026-02-06
**Severity:** Critical
**Symptom:** Screen goes black and game locks up when transitioning between dungeon rooms during casual exploration.
**Reproducibility:** Intermittent (likely correlated with rooms that draw torches during load).
**Status:** Still reproduces on the latest ROM (2026-02-06). Torch-loop register-width fix is correct but not sufficient.

**Attempted fix (NOT VALIDATED — bug still reproduces):**
- Removed `SEP #$30` before re-entering the vanilla torch draw loop at `$0188C9` (that loop runs in **16-bit** mode).
- Preserved `P/A/X/Y` around the injected `JSL WaterGate_CheckRoomEntry` so this hook returns with **vanilla** flags/register state (notably `Z=1` from the sentinel compare).
- These changes are reasonable but UNPROVEN. The bug still occurs, so either there's a second cause, the analysis was wrong, or the fix has its own bug.

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

## Suspected Cause (UNCONFIRMED — no runtime evidence)

The hook previously executed `SEP #$30` on the `.draw_next_torch` path and then `JML $0188C9`.

That re-entered the vanilla torch loop with **M/X=8-bit**, but the loop contains 16-bit immediates like `CMP.w #$FFFF`. In 8-bit mode, the CPU consumes the wrong number of operand bytes and desynchronizes the instruction stream, which can present as a black screen + softlock/hang.

Secondary correctness issue: adding `JSL WaterGate_CheckRoomEntry` on the exit path clobbered processor flags and registers right before `RTL`. Vanilla returns immediately with `Z=1` from the sentinel compare; preserving `P/A/X/Y` keeps this hook transparent.

---

## Code Changes Applied (NOT VALIDATED — bug still reproduces)

**File:** `Dungeons/Collision/water_collision.asm`

- `.draw_next_torch`: jump back to `$0188C9` without changing M/X.
- Exit path: `SEP #$30` (vanilla), then save/restore `P/A/X/Y` around `JSL WaterGate_CheckRoomEntry`.

---

## Quick Validation

1. Rebuild with the fix and try repeated dungeon room transitions (include rooms with torches).
2. It still reproduces on the latest ROM, so we need deeper capture.
3. Disable the water gate system to confirm correlation:

```asm
; Config/feature_flags.asm
!ENABLE_WATER_GATE_HOOKS             = 0
!ENABLE_WATER_GATE_OVERLAY_REDIRECT  = 0
```

---

## New Debugging Plan (Mesen2 socket API)

Goal: capture enough ground truth at the moment of failure to answer:
- Is the screen forced-blanked? (`INIDISP` mirror at `$7E001A` == `$80`)
- Are we stuck in a transition module/submodule? (`$7E0010/$7E0011`)
- Are we hung in a tight loop (PC not advancing), or alive-but-stuck (PC advances, mode doesn't)?
- Who last wrote the values that kept us black (write attribution via `mem-blame`)?

### TL;DR (use the capture script)

```bash
# Before reproducing:
python3 scripts/capture_blackout.py arm --save-seed --assert-jtl

# After blackout occurs (do NOT reset emulator):
python3 scripts/capture_blackout.py capture

# Review recent captures:
python3 scripts/capture_blackout.py summary
```

If you want a wider net (fade + stack + color math), add `--deep` to both `arm` and `capture`.

### 0. Preflight (pick the right instance)
If multiple sockets exist, target explicitly:

```bash
export MESEN2_SOCKET_PATH=/tmp/mesen2-<yours>.sock
python3 scripts/mesen2_client.py health
python3 scripts/mesen2_client.py diagnostics
```

### 1. Make a Repro Seed State (library)
When you're in a dungeon near a doorway where this happens frequently:

```bash
python3 scripts/mesen2_client.py smart-save 20
python3 scripts/mesen2_client.py lib-save "Blackout repro seed" -t dungeon -t blackout -t repro
```

Keep the returned `state_id` so we can reload consistently (`lib-load <state_id>`).

### 2. Arm Instrumentation (before reproducing)
Start these once per session:

```bash
python3 scripts/mesen2_client.py p-watch start --depth 8000
python3 scripts/mesen2_client.py trace --action start --clear

# JumpTableLocal ($008781) requires X/Y=8-bit on entry; 16-bit causes stack corruption and black screens.
python3 scripts/mesen2_client.py p-assert 0x008781 0x10 --mask 0x10

python3 scripts/mesen2_client.py mem-watch add --depth 4000 0x7E0013  # INIDISP queue (INIDISPQ)
python3 scripts/mesen2_client.py mem-watch add --depth 4000 0x7E001A  # INIDISP mirror
python3 scripts/mesen2_client.py mem-watch add --depth 4000 0x7E0010  # GameMode
python3 scripts/mesen2_client.py mem-watch add --depth 4000 0x7E0011  # SubMode
python3 scripts/mesen2_client.py mem-watch add --depth 4000 0x7E00A0  # Underworld room layout index
python3 scripts/mesen2_client.py mem-watch add --depth 4000 --size 2 0x7E00A4  # Room ID (16-bit)
```

Optional (if it looks like a color-math/palette bug rather than forced blank):

```bash
python3 scripts/mesen2_client.py mem-watch add --depth 4000 0x7E009A
python3 scripts/mesen2_client.py mem-watch add --depth 4000 0x7E009C
python3 scripts/mesen2_client.py mem-watch add --depth 4000 0x7E009D
```

### 3. Reproduce Until the Screen Goes Black (do not reset)
Once it happens, immediately capture:

```bash
python3 scripts/mesen2_client.py smart-save 21
python3 scripts/mesen2_client.py savestate-label set 21 --label blackout

python3 scripts/mesen2_client.py capture --json > /tmp/oos_blackout_capture.json
python3 scripts/mesen2_client.py cpu --json > /tmp/oos_blackout_cpu.json
python3 scripts/mesen2_client.py stack-retaddr --count 12 --json > /tmp/oos_blackout_stack.json

python3 scripts/mesen2_client.py p-log --count 200 --json > /tmp/oos_blackout_p_log.json

python3 scripts/mesen2_client.py mem-read --len 1 0x7E0013 --json > /tmp/oos_blackout_inidispq.json
python3 scripts/mesen2_client.py mem-read --len 1 0x7E001A --json > /tmp/oos_blackout_inidisp.json
python3 scripts/mesen2_client.py mem-read --len 1 0x7E0010 --json > /tmp/oos_blackout_mode.json
python3 scripts/mesen2_client.py mem-read --len 1 0x7E0011 --json > /tmp/oos_blackout_submode.json
python3 scripts/mesen2_client.py mem-read --len 2 0x7E00A4 --json > /tmp/oos_blackout_room_id.json

python3 scripts/mesen2_client.py mem-blame --addr 0x7E0013 --json > /tmp/oos_blackout_inidispq_blame.json
python3 scripts/mesen2_client.py mem-blame --addr 0x7E001A --json > /tmp/oos_blackout_inidisp_blame.json
python3 scripts/mesen2_client.py mem-blame --addr 0x7E0010 --json > /tmp/oos_blackout_mode_blame.json
python3 scripts/mesen2_client.py mem-blame --addr 0x7E0011 --json > /tmp/oos_blackout_submode_blame.json
python3 scripts/mesen2_client.py mem-blame --addr 0x7E00A0 --json > /tmp/oos_blackout_room_blame.json

python3 scripts/mesen2_client.py disasm --count 40 --json > /tmp/oos_blackout_disasm.json
python3 scripts/mesen2_client.py trace --count 100 --json > /tmp/oos_blackout_trace.json
```

### 4. Interpret the Capture
- If `$7E001A` is `$80` and the last writer PC is the normal transition forced-blank, the bug is likely "transition never reached unblank/fade-in". Look at `GameMode/SubMode`, and PC/stack to find where we stalled.
- If `GameMode` is stuck at a loading module (often `$06`) with `SubMode` not progressing, focus on `Module06_UnderworldLoad` state machine.
- If PC is stable (or trace shows a tiny repeating sequence), focus on the tight loop and why its exit condition never becomes true.

### 5. Optional: Fast A/B Isolation (feature flags)
If the capture implicates the water gate hooks, rebuild with:

```asm
!ENABLE_WATER_GATE_HOOKS             = 0
!ENABLE_WATER_GATE_OVERLAY_REDIRECT  = 0
```

If the blackout persists with those OFF, the root cause is elsewhere (widen the capture to transition modules and INIDISP writers).

---

## Related Files

| File | Role |
|------|------|
| `Dungeons/dungeons.asm` | Hook site (org $0188DF) |
| `Dungeons/Collision/water_collision.asm` | Hook implementation |
| `Config/feature_flags.asm` | `!ENABLE_WATER_GATE_HOOKS` toggle |
| `scripts/mesen2_client.py` | Mesen2 socket API client |
| `scripts/capture_blackout.py` | Automated Phase 1 evidence capture |
