# Overworld / Dungeon Softlock — Investigation Alternatives

**Purpose:** Alternatives to “patch every call site” or “find the single corrupting instruction” for resolving the black-screen softlock. Use when dynamic capture is difficult or to complement it.

**Status:** Reference only. Prefer finding the true root cause via dynamic capture or module isolation; these options are fallbacks or parallel strategies.

---

## Hypothesis conflict (clarify first)

Docs disagree on whether JumpTableLocal X=8-bit is the bug or expected:

| Doc | Claim |
|-----|--------|
| [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) | PLY with X=8-bit pops 1 byte → stack misalignment → wrong return. |
| [RootCause_Investigation_Handoff.md](RootCause_Investigation_Handoff.md) | JumpTableLocal **requires** X=8-bit (PLY pops 1, then REP #$30 + PLA pops 2 = 3 bytes). X=8 is correct; focus on **SP corruption** to 0x0Dxx. |

**Action:** Disassemble vanilla routine at `$00:8781` (bank 00) and confirm the exact sequence (PLY, REP, PLA, etc.). Then either (a) treat X=8 as correct and focus on **what corrupts SP**, or (b) treat PLY width as the bug and fix **JumpTableLocal once** (see Alternative 2).

---

## Alternative 1: Find what corrupts SP (not $7E1F0A)

If RootCause_Investigation_Handoff is right, **SP** is corrupted (e.g. TCS with bad A or stack overflow) **before** NMI; NMI then saves that bad SP to `$7E1F0A`. A write watch on `$7E1F0A` may only see NMI’s save, not the original corrupting instruction.

**Alternatives:**

1. **Conditional breakpoint on TCS**
   - Break when `TCS` executes **and** A is outside 0x01xx (e.g. `A >= 0x0200` or `A >= 0x0D00`).
   - Requires Mesen2 (or script) to support conditional breakpoints on instruction + register.
   - Captures the exact TCS that sets SP to a bad value.

2. **SP polling with trace**
   - Already in `repro_stack_corruption.py --strategy polling`: advance one frame at a time, read SP; when SP leaves 0x01xx, capture trace.
   - Use the trace to find the **last** instruction that had valid SP and the **next** that had bad SP; that next instruction (or the one that changed A before TCS) is the culprit.

3. **Break on NMI entry when SP is already bad**
   - Break at NMI entry (e.g. `$0082CE`) when `SP >= 0x0200` (or `SP < 0x0100`).
   - Then inspect call stack / trace backward to see what in the main loop last ran before NMI. Less precise than TCS conditional breakpoint but no special condition support needed.

---

## Alternative 2: Fix JumpTableLocal once (if PLY width is the bug)

If the real bug is “PLY with X=8-bit pops 1 byte and misaligns the stack,” fix the **routine** at `$008781` so it always pulls 3 bytes for the JSL return, regardless of X:

- **Option A:** Patch at `$008781`: insert `REP #$10` before `PLY` (and `SEP #$10` after if the rest of the routine assumes 8-bit Y). Then PLY always pops 2 bytes; ensure the following stack read (e.g. PLA) is adjusted so total = 3 bytes.
- **Option B:** Replace the routine with a JSL to an Oracle stub in free space that does: save P, force 16-bit index, pull return address (e.g. PLA/PLA/PLA or PLY+PLA as needed), JMP to table entry, then RTL. One patch at `$008781`, one stub; all call sites unchanged.

**Requires:** Disassembly of `$00:8781` (and a few bytes after) to see exact bytes and avoid breaking vanilla callers. Usdasm or z3dk may have bank 00.

---

## Alternative 3: Git bisect (find introducing commit)

The instability correlates with Nov 2025 – Jan 2026 commits. Bisect to find the first bad commit:

```bash
git bisect start
git bisect bad HEAD
git bisect good <last-known-good-commit>   # e.g. before 8b23049
# For each midpoint:
./scripts/build_rom.sh 168
# Load state 1 in Mesen2, run ~2 min or until black screen
git bisect good   # or bad
git bisect reset
```

**Key commits to test manually if bisect is noisy:** `8b23049` (menu), `93bd42b` (time system), `d41dcda` (ZSOW v3).

**Outcome:** Narrow to one commit; diff that commit and fix the introduced bug.

---

## Alternative 4: Module isolation (binary search)

Already in [Module_Isolation_Plan.md](Module_Isolation_Plan.md). Disable one module at a time (menu → overworld → sprites/masks/items), rebuild, test. When the crash disappears, the last-disabled module contains the bug; then narrow within that module (e.g. disable sub-features or use dynamic capture with that build).

**Pros:** No need to catch the exact instruction first. **Cons:** Needs a clear repro; disabling can break the build if dependencies are missing.

---

## Alternative 5: NMI SP validation (safety net only)

Patch the NMI handler so that before `LDA $1F0A : TCS`, it checks that the value in `$7E1F0A` is in 0x01xx; if not, use a default (e.g. 0x01FF) or skip the TCS. Prevents black screen from **any** SP corruption but does not fix the root cause.

**Use only as:** A temporary mitigation while investigating, or a last resort. Can hide the bug and make dynamic capture harder.

---

## Alternative 6: ROM diff vs known-good

If a known-good ROM exists (e.g. before Nov 2025):

- Binary diff against current ROM, focus on bank $00 (NMI, JumpTableLocal), bank $06 (sprite/HUD hooks), and any bank that contains Oracle hooks in the crash chain.
- Identifies what **changed**; then audit those changes for P/SP/stack bugs.

---

## Summary

| Alternative | What it finds / does | Effort |
|-------------|----------------------|--------|
| 1a. TCS conditional breakpoint | Instruction that sets SP to bad value | Low if supported |
| 1b. SP polling + trace | Frame and instruction where SP goes bad | Medium (script exists) |
| 1c. Break at NMI when SP bad | Approximate main-loop culprit | Low |
| 2. Fix JumpTableLocal at $008781 | Single routine fix for PLY width | Medium (need disasm) |
| 3. Git bisect | Introducing commit | Medium |
| 4. Module isolation | Module that contains bug | Low–medium |
| 5. NMI SP validation | Symptom only (safety net) | Low |
| 6. ROM diff | Changed code regions | Low |

**Recommended order:** Resolve hypothesis (disassemble $008781) → then either (A) focus on SP corruption (1a/1b/1c + dynamic capture) or (B) fix JumpTableLocal once (2). Use 3 or 4 if capture is inconclusive.
