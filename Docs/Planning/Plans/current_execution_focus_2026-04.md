# Oracle of Secrets - Current Execution Focus (April 2026)

Status: Active
Audience: Solo dev + agents
Purpose: One practical "what to do next" page for testing, progression, and plot.

---

## What Changed Since Earlier Plans

- Tooling exists; the main blocker is runtime validation throughput.
- Multiple progression systems are "code complete, untested".
- Story docs are strong, but critical path implementation still has gaps
  (especially D7 rescue and shrine reward correctness).

---

## Immediate Priority Stack (Do In Order)

1. Establish runtime test loop that actually runs (Mesen2 socket attached).
2. Validate progression core (`GetCrystalCount`, `UpdateMapIcon`,
   `SelectReactionMessage`) through Maku Tree thresholds.
3. Fix known progression data defects (S1/S2 pendant mismatch).
4. Close the biggest narrative pipeline gap (D7 Farore rescue scaffold).
5. Replace remaining critical-path placeholder dialogue.

---

## 1) Runtime Testing Sprint (First 2 Sessions)

Goal: Convert "untested" into "tested + logged" for high-risk systems.

### Session A (60-90 min): Harness Bring-Up

- Launch isolated Mesen2 instance and confirm socket diagnostics.
- Run `scripts/run_regression_tests.sh regression` with emulator attached.
- Capture raw results in a status note under `Docs/Planning/Status/`.

Definition of done:
- Regression script executes tests (not skipped for missing backend).
- You have a pass/fail list, not "unknown".

### Session B (90-120 min): Progression Core Validation

Manual/runtime checks:

1. Maku Tree hint cascade at crystal counts `0, 1, 3, 5, 7`.
2. Confirm message selection correctness for each threshold.
3. Confirm `MapIcon` progression changes as expected per threshold.
4. Smoke-check Village Elder post-D1 guidance branch.

Definition of done:
- `Core/progression.asm` helpers move from untested to validated (or logged
  with exact failures).

---

## 2) Progression Logic Fixes (After Validation)

### High Value, Low Risk

1. S1 chest item fix: room `0x7A` pendant `0x38 -> 0x39`.
2. S2 chest item fix: room `0x73` pendant `0x39 -> 0x3A`.
3. Re-verify with `z3ed chest-inventory` and one runtime pickup path each.

Why first:
- These are concrete progression correctness defects.
- They unblock Master Sword path confidence.

---

## 3) Plot-Critical Implementation Focus

### Must-Have Narrative Pipeline

1. D7 post-boss rescue flow:
   - Crystal drop and progression flag setter.
   - `GameState_FaroreRescued = 0x03` setter path.
   - Runtime callsite for Farore rescue dialogue.
   - Post-rescue Farore states in Hall of Secrets.

2. Critical-path dialogue placeholders:
   - Maku remaining slots: `$1C8`, `$1C9`, `$1CB`.
   - D3 prison sequence: `$1CC-$1D1`.
   - Gossip placeholders are lower priority for RC unless used in main path.

Definition of done:
- Main story beats are understandable without placeholder text.
- D7 completion clearly unlocks intended endgame flow.

---

## 4) Suggested Work Menu By Energy

Low focus (15-45 min):
- Write/replace one placeholder dialogue cluster.
- Update one NPC progression response table.
- Log one concise runtime result note in `Docs/Planning/Status/`.

Medium focus (1-2 hrs):
- Run one full targeted test batch (Maku + water gate).
- Implement/verify one progression flag path.
- Patch and validate one shrine pendant correction flow.

High focus (2-4 hrs):
- D7 rescue sequence integration pass.
- D4 water gate full regression and persistence validation.
- D8/S3 ownership + boss-path clarification if starting shrine endgame push.

---

## 5) Documentation Cleanup Rules (Going Forward)

- Keep one "now" doc only (this file) and update it weekly.
- Keep strategy in `release_timeline_2026.md`, not duplicated elsewhere.
- Move old snapshots to `Status/` instead of rewriting long plan docs.
- Mark historical docs explicitly as historical when superseded.

---

## Next 3 Concrete Tasks

1. Run runtime regression with emulator attached and log results.
2. Execute Maku threshold test matrix and log message/icon outcomes.
3. Apply and verify S1/S2 pendant data fixes.
