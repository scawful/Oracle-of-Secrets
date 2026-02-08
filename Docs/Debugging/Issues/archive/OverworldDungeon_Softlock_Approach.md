# Approach: Overworld and Dungeon Softlocks (Sprite-Related, Elusive)

**Purpose:** How to approach the overworld and dungeon softlocks that are sprite-related and hard to pin down. Use this alongside [Root_Cause_Debugging_Workflow.md](../Tooling/Root_Cause_Debugging_Workflow.md) and the existing handoff/plan docs.

---

## Why These Bugs Feel Elusive

1. **Intermittent** – Same savestate + same actions don’t always trigger; timing (NMI, frame, sprite tick) matters.
2. **Sprite- and context-dependent** – Different rooms have different sprite sets; the crash chain goes through sprite dispatch (JumpTableLocal, X=8-bit) and width imbalances are concentrated in sprite routines (Oracle_Ancilla_CheckDamageToSprite, Oracle_ApplyRumbleToSprites, etc.).
3. **Two distinct bugs** – **State 1** = overworld softlock; **State 2** = file-load dungeon freeze. Track and repro them separately.
4. **Static fixes didn’t fix** – SEP #$30→$20 in sprite dispatch, PHP/PLP wrappers, and other targeted fixes were applied but the crash persists. Root cause is still **unknown** (likely one instruction corrupting SP to 0x0Dxx).
5. **Heavy refactors in the path** – Time system, menu, and ZSOW had large AI-assisted rewrites (Nov 2025–Jan 2026); any of these can introduce path-dependent P/stack behavior that only shows under specific sprite/timing conditions.

So elusiveness comes from: **many variables (sprites, room, frame) + a single bad instruction that only executes in certain paths**.

---

## Recommended Approach (In Order)

### 1. Lock Down Reproducibility First

Without a stable repro, isolation and capture are unreliable.

- **Separate the two bugs.**  
  - **Overworld (State 1):** One savestate + one short sequence (e.g. “load slot 1, press A, walk north 3 seconds”) that you document. If it doesn’t fire every time, note “repro ~N% of the time” and still use it.  
  - **Dungeon (State 2):** Same idea: one savestate (file-load dungeon) + one sequence; document and keep it separate.

- **Savestate checklist.**  
  Keep a few “known good” savestates (boot, after load, after key event). When it softlocks, reload the last good one and shorten the repro to the **shortest** sequence that still triggers. See [OverworldSoftlock_LessCerebralOptions.md](OverworldSoftlock_LessCerebralOptions.md) §5.

- **Golden path.**  
  Define one path that “must never softlock” (e.g. start → overworld → first dungeon door). Use it as the **only** regression test until it’s solid. Reduces variables and gives a clear pass/fail. See [OverworldSoftlock_Plan.md](OverworldSoftlock_Plan.md) Path 3.

- **Optional: on-screen SP (or $7E1F0A).**  
  If you can show SP (and/or NMI SP save `$7E1F0A`) on screen during play, when it softlocks you see the last value without attaching a debugger. Helps confirm “when” and “where.” See [OverworldSoftlock_LessCerebralOptions.md](OverworldSoftlock_LessCerebralOptions.md) §4.

Once you have “same state + same actions → softlock often enough,” move to isolation.

---

### 2. Isolate by Module (Sprite vs Time vs Menu vs OW)

Narrow *which system* is in the failing path. That makes the bug less “elusive” by removing variables.

- **Module isolation (recommended).**  
  Disable one major system at a time, rebuild, then run the **same** repro (same savestate + same sequence):

  - `python3 scripts/set_module_flags.py --disable sprites,masks,items` then build → if overworld softlock **disappears**, sprites (or ancilla/items) are in the path.  
  - `--disable overworld` → time system / ZSOW.  
  - `--disable menu` → menu/HUD path (and file-load path for State 2).

  See [Module_Isolation_Plan.md](Module_Isolation_Plan.md). Automated: `./scripts/run_module_isolation.sh --auto` (or `run_module_isolation_auto.py`).

- **Interpretation.**  
  If disabling **sprites** removes the softlock, the bug is sprite-path-dependent (dispatch, width imbalance in a sprite routine, or a routine called from sprite code). You then focus on sprite routines from static analysis (see [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) “Prioritized Fix Candidates” and “Bank 06 sprite routines”).

  If disabling **overworld** removes it, focus on ZSOW / time system / LoadOverworldSprites.  
  If disabling **menu** removes State 2, focus on menu/file-load path.

---

### 3. Dynamic Capture: Catch the Exact Instruction

The only way to stop the elusiveness for good is to **see** the instruction that corrupts SP (or that leads to it). Static analysis has already narrowed the mechanism (SP → 0x0Dxx → DBR=0x50 → main dispatch in RAM); what’s missing is the **PC** of the corrupting instruction.

- **Conditional breakpoint on SP.**  
  Break when `sp >= 0x0200` (or, if supported, on TCS with `a >= 0x0200`). Load your **repro savestate**, run the **repro sequence**; when the breakpoint fires, you’re at or just after the bad instruction. Then: TRACE, STACK_RETADDR, P_LOG, and SYMBOLS_RESOLVE / z3ed on that PC. See [RootCause_Investigation_Handoff.md](RootCause_Investigation_Handoff.md) “Step 1: Watch SP for the Corruption Write.”

- **Repro script.**  
  Use the same savestate + sequence with the script that sets up the breakpoint and captures attribution on hit:

  ```bash
  cd ~/src/hobby/oracle-of-secrets
  python3 scripts/repro_stack_corruption.py --strategy auto --output /tmp/blame_report.json
  ```

  For overworld: default (slot 1). For dungeon: `--slot 2 --press-a`. If “auto” doesn’t fire, try:

  ```bash
  python3 scripts/repro_stack_corruption.py --strategy polling --frames 600 --output /tmp/blame_report.json
  ```

  See [Root_Cause_Debugging_Workflow.md](../Tooling/Root_Cause_Debugging_Workflow.md) Phases 3–5.

- **Map PC to source.**  
  Once you have the PC: SYMBOLS_RESOLVE (socket), z3ed `rom-resolve-address`, Hyrule Historian, and `rg` in oracle-of-secrets ASM. Check if that routine is one of the sprite/width-imbalance routines from static analysis.

---

### 4. Reduce Variables While Debugging

- **Feature freeze.**  
  Pause new overworld/sprite features; only fix regressions on the path you’re debugging. Fewer moving parts makes it easier to see if a change helps. See [OverworldSoftlock_LessCerebralOptions.md](OverworldSoftlock_LessCerebralOptions.md) §8.

- **Bisect (if you have a known-good commit).**  
  If you have an older build that doesn’t softlock on the **same** route:

  ```bash
  git bisect run python3 scripts/bisect_softlock.py
  ```

  Then inspect the introducing commit (and that diff) for sprite/time/menu changes. See [OverworldSoftlock_Plan.md](OverworldSoftlock_Plan.md) Path D.

- **One fix, then test.**  
  Prefer one small, targeted fix (e.g. one routine’s PHP/PLP or width restore), then run the **same** repro again. If softlocks drop, you’ve found a contributing path; if not, you haven’t hidden the root cause behind a broad “fix.” See [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) “Root cause first (do not paper over).”

---

## Summary

| Goal | Action |
|------|--------|
| **Reproducibility** | Separate State 1 vs State 2; savestate checklist; golden path; optional on-screen SP. |
| **Less elusive** | Module isolation (disable sprites / overworld / menu); see which system removes the softlock. |
| **Root cause** | Dynamic capture: conditional breakpoint `sp >= 0x0200` (or polling), then TRACE + resolve PC to source. |
| **Fewer variables** | Feature freeze on OW/sprite; bisect if you have a good commit; one fix at a time. |

The sprite-related elusiveness is mostly **many code paths (different sprites/rooms/frames) and one or a few bad instructions**. Lock repro, isolate by module, then catch the exact PC with the existing repro script and workflow; after that, fix that place instead of adding more defensive wrappers.

---

## References

- [Root_Cause_Debugging_Workflow.md](../Tooling/Root_Cause_Debugging_Workflow.md) – Six-phase workflow and tool inventory.
- [RootCause_Investigation_Handoff.md](RootCause_Investigation_Handoff.md) – Mechanism, evidence, and capture commands.
- [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) – Static analysis, prioritized routines, repro script strategies.
- [Module_Isolation_Plan.md](Module_Isolation_Plan.md) – How to disable modules and interpret results.
- [OverworldSoftlock_LessCerebralOptions.md](OverworldSoftlock_LessCerebralOptions.md) – Play-and-log, golden path, on-screen debug, feature freeze.
- [OverworldSoftlock_Plan.md](OverworldSoftlock_Plan.md) – Paths (play-and-log, golden path, isolation, bisect).
