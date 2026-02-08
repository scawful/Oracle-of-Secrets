# Bug: Dungeon Transition Blackout / Softlock

**Reported:** 2026-02-06
**Severity:** Critical
**Symptom:** Screen goes black and game locks up when transitioning between dungeon rooms during casual exploration.
**Reproducibility:** Intermittent (likely correlated with rooms that draw torches during load).
**Status:** INVESTIGATING (reopened 2026-02-07).

**Attempted fix (not the root cause):**
- Removed `SEP #$30` before re-entering the vanilla torch draw loop at `$0188C9` (that loop runs in **16-bit** mode).
- Preserved `P/A/X/Y` around the injected `JSL WaterGate_CheckRoomEntry` so this hook returns with **vanilla** flags/register state (notably `Z=1` from the sentinel compare).
- These changes are still reasonable, but the blackout persisted because **at least one** culprit was elsewhere.

**Root cause (one confirmed contributor):** `CustomRoomCollision` hook (`org $01B95B`, `Dungeons/Collision/custom_collision.asm`) executed `REP #$30` and could return to vanilla without restoring `P` (M/X register width + flags) on the early-out path (no custom collision data for the room).

**Fix applied:** Preserve/restore `P` inside `CustomRoomCollision` via `PHP`/`PLP` so the hook becomes width-transparent to the caller.
- Commit: `b59959f` (`fix: preserve P (M/X width) in CustomRoomCollision hook`)

**But:** Dungeon blackouts were still observed after this fix on later ROMs, which implies either:
- The ROM under test did not include the fix (ROM parity issue), or
- There is a second, independent blackout cause (most likely another register-width leak into a transition/jump-table routine).

## New Hypothesis (Unverified): 8-bit Width Contract Violation Near $09A19C

There is a concrete "simple mistake" class that can produce intermittent blackouts even when you have **no follower/cart**:

- The Zora Baby transition hook at `$09A19C` overwrites `LDX $10 : LDY $11` in `Follower_BasicMover`.
- Vanilla code immediately after (`$09A1A0+`) performs `CPY.b` / `CPX.b` comparisons with **8-bit immediates**.
- If a prior routine leaks `X=16` or `M=16` into this block, the CPU can desync immediates and/or corrupt the stack (black screen / hang symptoms).

**Fix applied (width hardening):** `CheckForZoraBabyTransitionToSprite` now forces `SEP #$30` and exits with M/X=8 (while restoring flags via `PLP`).

File: `Sprites/NPCs/followers.asm` (`CheckForZoraBabyTransitionToSprite`)

## Second High-Probability Culprit (History-Based Inference)

There is a separate, concrete, “simple mistake” class that matches a black-screen-on-transition symptom and does **not** require a follower/cart:

- `Graphics_Transfer` is hooked into `UnderworldTransition_ScrollRoom` at `$02BE5E` (`Core/patches.asm` → `Sprites/all_sprites.asm`).
- In room index `$5A`, it calls `ApplyManhandlaGraphics`/`ApplyManhandlaPalette` (`Sprites/Bosses/manhandla.asm`) during the scroll/transition path.

Historically, `ApplyManhandlaGraphics` was **not safe if X/Y were 16-bit**:
- `PHX` size depends on X width, but the routine ended with `SEP #$30` and then `PLX` (stack shift if X=16-bit on entry).
- More importantly: it wrote to PPU regs via `STX $2100/$2115/$420B/...` without forcing X=8-bit. If X=16-bit, `STX` writes **two bytes** and can corrupt neighboring PPU regs.

This exact failure mode is consistent with “intermittent transition blackout” because it can trash display state or the stack during scroll.

**Fix (unvalidated against your specific repro):**
- Force X/Y to 8-bit inside `ApplyManhandlaGraphics` via `PHP : SEP #$10` and `PLP` on exit.
- Make `Graphics_Transfer` preserve DB/X/Y/P and re-emit the vanilla `LDA $11 : CMP #$02` flags for the caller branch.

Files:
- `Sprites/Bosses/manhandla.asm` (ApplyManhandlaGraphics)
- `Sprites/all_sprites.asm` (Graphics_Transfer wrapper)

## Another Concrete Culprit Class: Transition Hook Width Mismatch (Follower/Minecart)

Even if you have no follower/cart active, the minecart/follower system installs hooks into the **transition modules**:

- `Module07_02_01_LoadNextRoom` at `$028A5B` (inter-room transitions)
- `UnderworldTransition_Intraroom_PrepTransition` at `$0289BF` (intra-room transitions)

The `$0289BF` hook site is inside a `REP #$20` region (A=16). A common "simple mistake"
is to execute **8-bit immediates** (e.g. `LDA.b #$0B`) or read an 8-bit flag as a 16-bit
value while M=16, which can:
- desynchronize the instruction stream if an 8-bit immediate is assembled but the CPU expects 16-bit immediate
- mis-detect a flag because it reads an unintended high byte

Fix pattern used:
- Do the replaced vanilla `STA.l $7EC007` store first (so it stays 16-bit like vanilla)
- `PHP`/`PLP` + temporarily `SEP #$20` inside the hook for any 8-bit flag/immediate logic

---

## Previously Suspected: Water Gate Room Load Hook (Not Culprit)

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

## Validation

1. Confirm ROM parity (the ROM you're testing includes the intended bytes at the relevant hook sites).
2. Rebuild and try repeated dungeon room transitions (include rooms with torches).
3. If blackout reproduces: run the capture workflow below and treat this doc as active again.

### Quick Parity Checks (No Emulator)
These sanity checks prevent “testing the wrong ROM”:
- `CustomRoomCollision` hook is present at `$01B95B` (JSL to `CustomRoomCollision`).
- `Underworld_LoadRoom_ExitHook` at `$0188DF` jumps back to `$0188C9` without `SEP #$30` on the loop path.

### Strong Current Hypothesis (Needs Capture To Confirm)
The most common *remaining* cause of black-screen softlocks is an **X/Y width leak into `JumpTableLocal`** (`$008781`).
If `X/Y` are 16-bit on entry, `PLY` consumes the wrong number of bytes and corrupts the stack, often manifesting as a blackout.

Use the capture script with `--assert-jtl` to confirm or rule this out quickly.

Mitigation/safety net:
- `!ENABLE_JUMPTABLELOCAL_GUARD` (default ON) patches `$008781` to force `SEP #$10` before the first `PLY`.
- If you want to *find the upstream leak*, temporarily set it to `0` and reproduce with `--assert-jtl`.

```asm
; Config/feature_flags.asm
!ENABLE_WATER_GATE_HOOKS             = 0
!ENABLE_WATER_GATE_OVERLAY_REDIRECT  = 0
```

---

## Debugging Plan (Keep For Future Regressions)

Goal: capture enough ground truth at the moment of failure to answer:
- Is the screen forced-blanked? (`INIDISPQ` at `$7E0013` has bit 7 set, often `$80`)
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

### Fast Agent Workflow (No Path-Pasting)

If you can get the bug to reproduce from a fixed “one action away” seed state, prefer the deterministic repro + ddmin bisect helpers.

1. Create a library seed once (near the transition that blackouts):

```bash
python3 scripts/mesen2_client.py lib-save "Zora Temple stairs repro seed" -t dungeon -t blackout -t repro
python3 scripts/mesen2_client.py library --json | rg -n \"Zora Temple stairs\"  # grab the state_id
```

2. Deterministic repro (loads seed from library, presses DOWN, captures + triages on anomaly):

```bash
python3 scripts/repro_blackout_transition.py --lib <state_id> --arm
```

3. Feature-flag ddmin bisect (find the minimal disables that stop reproducing):

```bash
python3 scripts/bisect_blackout_flags.py --lib <state_id> --runs 2 --no-capture --arm
```

If Mesen2 isn’t already running, add `--launch --instance oos-blackout` to either command.

**Important address note:** `$7E001A` is the vanilla frame counter (`FRAME`), not `INIDISP`. For black screens, watch/blame `INIDISPQ` at `$7E0013` (queued value written during NMI), and optionally read the PPU register `INIDISP` at `$002100` for ground truth.

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
python3 scripts/mesen2_client.py mem-watch add --depth 4000 0x7E001A  # Frame counter (FRAME)
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
python3 scripts/mesen2_client.py mem-read --len 1 0x002100 --json > /tmp/oos_blackout_inidisp_ppu.json
python3 scripts/mesen2_client.py mem-read --len 1 0x7E0010 --json > /tmp/oos_blackout_mode.json
python3 scripts/mesen2_client.py mem-read --len 1 0x7E0011 --json > /tmp/oos_blackout_submode.json
python3 scripts/mesen2_client.py mem-read --len 2 0x7E00A4 --json > /tmp/oos_blackout_room_id.json

python3 scripts/mesen2_client.py mem-blame --addr 0x7E0013 --json > /tmp/oos_blackout_inidispq_blame.json
python3 scripts/mesen2_client.py mem-blame --addr 0x7E0010 --json > /tmp/oos_blackout_mode_blame.json
python3 scripts/mesen2_client.py mem-blame --addr 0x7E0011 --json > /tmp/oos_blackout_submode_blame.json
python3 scripts/mesen2_client.py mem-blame --addr 0x7E00A0 --json > /tmp/oos_blackout_room_blame.json

python3 scripts/mesen2_client.py disasm --count 40 --json > /tmp/oos_blackout_disasm.json
python3 scripts/mesen2_client.py trace --count 100 --json > /tmp/oos_blackout_trace.json
```

### 4. Interpret the Capture
- If `INIDISPQ` (`$7E0013`) is `$80` for a long time and the last writer PC is the normal transition forced-blank, the bug is likely "transition never reached unblank/fade-in". Look at `GameMode/SubMode`, and PC/stack to find where we stalled.
- If `GameMode` is stuck at a loading module (often `$06`) with `SubMode` not progressing, focus on `Module06_UnderworldLoad` state machine.
- If PC is stable (or trace shows a tiny repeating sequence), focus on the tight loop and why its exit condition never becomes true.

### 5. Optional: Fast A/B Isolation (feature flags)
If the capture implicates the water gate hooks, rebuild with:

```asm
!ENABLE_WATER_GATE_HOOKS             = 0
!ENABLE_WATER_GATE_OVERLAY_REDIRECT  = 0
```

If the capture implicates room-load/transition hooks (or you want a quick “is it one of our hooks?” sanity check), A/B these toggles one at a time:

```asm
; Disable custom underworld collision writer (restores vanilla $01B95B logic)
!ENABLE_CUSTOM_ROOM_COLLISION         = 0

; Disable minecart/follower transition hooks (restores vanilla $0289BF/$028A5B)
!ENABLE_FOLLOWER_TRANSITION_HOOKS     = 0

; Disable scroll-room hook at $02BE5E (restores vanilla LDA $11)
!ENABLE_GRAPHICS_TRANSFER_SCROLL_HOOK = 0
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
