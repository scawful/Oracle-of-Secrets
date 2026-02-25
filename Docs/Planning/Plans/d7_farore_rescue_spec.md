# D7 Farore Rescue Sequence — Design Spec

**Created:** 2026-02-13
**Status:** In Progress (feature-gated scaffold active)
**Owner:** TBD (ASM implementation)
**Depends on:** Kydrog boss fight working, message bank extension past 0x1BB
**Feature Flag:** `!ENABLE_D7_FARORE_RESCUE_SEQUENCE` (default `0`)
**Last Reviewed:** 2026-02-13
**Next Review:** 2026-02-20

---

## Context

The D7 Dragon Ship is the climax of the main quest arc (D1-D7). After defeating Kydrog, the player rescues Farore, which unlocks the pendant quest and path to the Master Sword. The boss fight exists, but the post-boss story pipeline is still a stub.

---

## Current State

### What Works
- Kydrog boss: 13 states, 4 phases, fully functional combat.
- Farore sprite: 8 states for intro sequence (pre-capture).
- Message `0x138` exists in `messages.org` (D7 crystal maiden slot).
- `!GameState_FaroreRescued = $03` exists in `Core/sram.asm`.

### What Is Missing
- `KydrogBoss_Death` now has a feature-gated staged scaffold, but still lacks spirit-flee/cutscene choreography.
- Progression setter exists, but commit timing is still tied to death-timer threshold rather than cutscene completion.
- Temporary dialogue slot (`0x138`) is used for the one-shot death message; dedicated Kydrog defeat text is still missing.
- Farore has no post-rescue states (8+).
- Crystal-maiden handoff/warp integration is not implemented yet.

---

## Implementation Status

- 2026-02-13: Step 1 scaffold landed in `Sprites/Bosses/kydrog_boss.asm`.
- `KydrogBoss_Death` now calls `KydrogBoss_Death_FaroreRescueScaffold` when `!ENABLE_D7_FARORE_RESCUE_SEQUENCE == 1`.
- 2026-02-13: Step 2 ordering landed: staged death flow in `SprMiscF` (`0=message`, `1=commit wait`, `2=committed`) with one-shot dialogue first, then guarded progression commit late in the death timer (`SprTimerA < $20`).
- `KydrogBoss_ApplyFaroreRescueProgression` sets `Crystals |= !Crystal_D7_DragonShip` and `GameState = !GameState_FaroreRescued` once per death sequence.

### Next Actions (Codex)
1. Replace temporary `!KydrogRescueMsg = $0138` with a dedicated Kydrog defeat slot once the message bank extension lands.
2. Add guarded crystal/maiden flow integration (or equivalent custom rescue handoff) so progression commit is tied to cutscene completion instead of timer threshold.
3. Add guarded Farore post-rescue state handling in `Sprites/NPCs/farore.asm` (states 8+).
4. Validate ON/OFF feature-flag behavior in Mesen2 (`GameState`, crystal bit, one-shot message behavior, and Hall-of-Secrets behavior).

---

## Feature Flag Guard (Required)

All new D7 rescue logic must be wrapped by `!ENABLE_D7_FARORE_RESCUE_SEQUENCE`.

- Flag OFF (`0`): current behavior remains unchanged (no new cutscene/flag writes).
- Flag ON (`1`): new D7 rescue sequence path is enabled.

Guard points:
1. `Sprites/Bosses/kydrog_boss.asm` (`KydrogBoss_Death`) entry path.
2. Any new helper that writes `GameState = $03`.
3. Any new Farore post-rescue state logic in `Sprites/NPCs/farore.asm`.

This keeps RC testing reversible and lets us isolate regressions quickly.

---

## Designed Sequence (6 Phases)

### Phase 1: Kydrog Defeat (`KydrogBoss_Death`)

Trigger: Kydrog HP reaches 0.

Needed behavior (flag ON only):
1. Keep `JSL Sprite_KillFriends`.
2. Play death SFX and freeze input briefly.
3. Show Kydrog defeat message (new multi-page message).
4. Play spirit-flee visual effect.
5. Despawn Kydrog cleanly.

### Phase 2: Farore Rescue Cutscene (crystal maiden flow)

Trigger: after Kydrog despawn.

Needed behavior:
1. Reuse standard boss-victory crystal flow.
2. Confirm/force message slot to use `0x138`.
3. Farore rescue text runs at correct timing.

### Phase 3: Flag Transitions (post-dialogue)

| Flag | Value | Purpose |
|------|-------|---------|
| `$7EF3C5` (`GameState`) | `$03` | Marks Farore rescued, unlocks endgame |
| `$7EF37A` (`Crystals`) | D7 bit set | D7 clear recorded |
| `$7EF300` (`KydrogFaroreRemoved`) | consistent post-rescue value | Prevent intro-state sprite behavior |

`GameState` progression remains:
- `$00` intro
- `$01` post-intro
- `$02` post-encounter
- `$03` Farore rescued

### Phase 4: Post-Boss Warp

Use vanilla post-boss warp if possible. Only add custom warp logic if the crystal flow fails to return player correctly.

### Phase 5: Hall of Secrets Farore NPC

Trigger: `GameState >= $03`.

Needed behavior:
1. Add Farore states 8+ in `farore.asm`.
2. State 8: first post-rescue exposition.
3. State 9: subsequent hint based on pendant progress.

### Phase 6: Endgame Unlock

After `GameState = $03`:
- Shrine guidance text path active.
- Maku Tree/related progression dialogue updates correctly.
- Any D7-dependent world gating reads the new state.

---

## Message Allocation

| ID | Content | Status |
|----|---------|--------|
| `0x138` | Farore D7 rescue speech | Exists; text should be finalized/validated |
| `0x1BC` (proposed) | Kydrog defeat speech | New |
| `0x1BD` (proposed) | Farore Hall exposition | New |
| `0x1BE` (proposed) | Farore repeat hint | New |

---

## Implementation Order (Flag-First)

1. Add `!ENABLE_D7_FARORE_RESCUE_SEQUENCE` to `Util/macros.asm` and `Config/feature_flags.asm`.
2. Add guarded staged scaffolding in `kydrog_boss.asm` (flag OFF returns current behavior).
3. Implement guarded `GameState = $03` transition helper.
4. Wire guarded post-boss message/cutscene transition.
5. Add guarded Farore post-rescue states (8+).
6. Validate ON/OFF matrix in Mesen2.

---

## Test Plan (Step 2)

### Build/Static Checks
1. `python3 scripts/verify_feature_flags.py --root .`
2. `./scripts/build_rom.sh 168` with default flags (rescue OFF).
3. `python3 scripts/check_zscream_overlap.py`
4. `python3 scripts/set_feature_flags.py --enable d7_farore_rescue_sequence` then `./scripts/build_rom.sh 168` (rescue ON compile gate).

### Runtime Checks (Mesen2)
1. Start from a pre-D7-clear state and defeat Kydrog with flag ON.
2. Confirm staged one-shot behavior during death:
   - `SprMiscF` transitions `0 -> 1 -> 2` for the Kydrog sprite.
   - rescue message triggers once at stage `0`.
3. Watch SRAM addresses:
   - `GameState` (`$7EF3C5`) becomes `$03` after the stage-1 death-timer threshold.
   - `Crystals` (`$7EF37A`) has bit `!Crystal_D7_DragonShip` set once.
4. Repeat with flag OFF and verify no new message/progression writes occur from this path.
5. Re-enter Hall of Secrets and confirm behavior remains unchanged until Farore states 8+ are implemented.

### Current Limitation
- Step 2 now enforces message-first/progression-second ordering, but still uses a temporary dialogue slot and does **not** yet provide full D7 rescue UX (true crystal-maiden handoff + Farore post-rescue NPC states).

### Validation Log (2026-02-13)
- `python3 scripts/verify_feature_flags.py --root /Users/scawful/src/hobby/oracle-of-secrets` passed before and after ON/OFF toggles.
- Flag OFF path: `./scripts/build_rom.sh 168` succeeded; `python3 scripts/check_zscream_overlap.py` succeeded.
- Flag ON path: `python3 scripts/set_feature_flags.py --enable d7_farore_rescue_sequence` then `./scripts/build_rom.sh 168` succeeded; `python3 scripts/check_zscream_overlap.py` succeeded.
- Flag restored to default OFF with `python3 scripts/set_feature_flags.py --disable d7_farore_rescue_sequence`.
- Static analysis reports remain non-fatal/high-volume existing debt; smoke tests were skipped because no Mesen2 backend was available.

---

## Validation Matrix

| Build Flag | Expected Result |
|------------|-----------------|
| OFF (`0`) | Current behavior unchanged; no `GameState=3` transition |
| ON (`1`) | Full D7 rescue pipeline executes and sets `GameState=3` |

Runtime checks:
1. Defeat Kydrog and verify transition to message/cutscene path.
2. Confirm `$7EF3C5 == $03` after rescue sequence.
3. Re-enter Hall of Secrets and verify Farore post-rescue dialogue state.
4. Rebuild with flag OFF and confirm legacy behavior is preserved.

---

## Risks

- D7 boss room spriteset mismatch must be fixed before reliable runtime validation.
- Crystal maiden flow may require tracing to confirm message routing.
- Message bank capacity above `0x1BB` still needs verification.

---

## References

- `Sprites/Bosses/kydrog_boss.asm`
- `Sprites/NPCs/farore.asm`
- `Core/sram.asm`
- `Config/feature_flags.asm`
- `Util/macros.asm`
- `Docs/World/Lore/kydrog_arc.md`
