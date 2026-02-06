# Oracle of Secrets 2026 Release Definition

This doc defines what a **full content release in 2026** means for Oracle of Secrets, and how to ship regular beta patches safely without losing weeks to avoidable ASM mistakes.

## Assumptions
- Core ROM content is already far ahead (room data, objects, dungeon layouts exist).
- Remaining work is primarily narrative polish, gameplay additions, final dungeon sequence, bug fixes, dungeon maps, credits, and tooling hardening.
- We will continue to ship **beta patches** to testers throughout 2026.
- Tooling exists but must be treated as guardrails, not optional.

---

## Release Types

### 1) Beta Patch (progress checkpoint)
**Purpose:** Frequent external playtesting and progress markers.

**Must include:**
- A working progression path for the targeted areas.
- Clear patch notes + known issues list.
- No new hardlocks on the golden path used for testers.

**Must pass (minimum):**
- `python3 scripts/test_runner.py --suite smoke`
- `python3 scripts/test_runner.py --tag transition` (if a transition system changed)
- `python3 ../z3dk/scripts/oracle_analyzer.py Roms/oos168x.sfc --hooks hooks.json --check-hooks --find-mx --find-width-imbalance --check-abi --check-phb-plb --check-jsl-targets --check-rtl-rts`

**Strongly recommended (catch regressions early):**
- Analyzer delta vs last known-good ROM (keep JSON outputs in `/tmp`, do not commit):
  - `python3 ../z3dk/scripts/oracle_analyzer.py Roms/oos168x_base.sfc --hooks hooks.json --json > /tmp/oos_an_base.json`
  - `python3 ../z3dk/scripts/oracle_analyzer.py Roms/oos168x.sfc      --hooks hooks.json --json > /tmp/oos_an_cur.json`
  - `python3 ../z3dk/scripts/oracle_analyzer_delta.py --baseline /tmp/oos_an_base.json --current /tmp/oos_an_cur.json`

**Nice to have:**
- A short highlight list of what is newly playable (1-3 bullets)
- Updated dungeon map docs for touched areas

---

### 2) Release Candidate (RC)
**Purpose:** Lock the content and hunt only bugs/perf/regressions.

**Must include:**
- All core dungeons playable end-to-end.
- Final dungeon sequence (or a locked stub if still in active dev; only allowed for pre-RC).
- All narrative beats in final text form for the full path.
- Credits and title flow in place.

**Must pass:**
- Full regression suite (`--suite regression`)
- All transition tests
- Lint in strict mode (or documented exceptions)

---

### 3) Full Release (2026)
**Definition of Done:**
- Complete story (no placeholder dialogue).
- All dungeons and final dungeon sequence playable.
- No known hardlocks in the golden path.
- Credits roll and postgame state handling.
- Dungeon maps published for every dungeon.
- Tooling and docs match the final behavior (no contradictions).

**Stop-ship bugs:**
- Any hardlock or black screen on the main progression path.
- Save corruption or invalid SRAM updates.
- Critical combat or physics regressions (e.g., stuck on interactions, forced resets).
- Room transitions that consistently break camera or player state.

---

## Caution Plan (ASM Safety)

### 1) Change isolation
- **One subsystem per commit** (Core/Overworld/Dungeons/Sprites/etc.).
- Avoid multi-area changes unless the change is shared infrastructure.
- Avoid "cleanup" + "behavior" in the same commit.

### 1.5) Feature isolation (hooks you can turn off)
- Prefer feature-gating risky `org` hooks instead of commenting them out.
- Canonical override: `Config/feature_flags.asm` (generate with `python3 scripts/set_feature_flags.py ...`).
- Keep tooling aligned: `scripts/build_rom.sh` regenerates `hooks.json` when flag files change so analyzer output matches the built ROM.

### 2) Mandatory guardrails for ASM edits
- Run analyzer (strict if possible):
  - `python3 ../z3dk/scripts/oracle_analyzer.py Roms/oos168x.sfc --hooks hooks.json --check-hooks --find-mx --find-width-imbalance --check-abi --check-phb-plb --check-jsl-targets --check-rtl-rts --strict`
- Run smoke tests when touching transitions or core hooks:
  - `python3 scripts/test_runner.py --suite smoke`

### 3) Hooks and annotations discipline
- Always add `@hook` + `@abi` tags for new entry points.
- Use `@watch` for new state or flags used in debugging.
- If a hook needs special width handling, document it in the comment and ensure analyzer expectations match.

### 4) "Two-step review" for high-risk files
**Files requiring review + lint + smoke tests before merge:**
- `Core/` (esp. `patches.asm`, `symbols.asm`, `sram.asm`)
- `Overworld/` (time system, transitions, ZSCustomOverworld)
- `Dungeons/` (room logic, object handlers, tags)

### 5) Pre-commit enforcement
- Ensure hooks are active: `git config core.hooksPath .githooks`
- Keep lint strict on staged ASM changes.

### 6) Beta patch safety checklist
- Lint (strict if symbols available)
- Smoke suite
- Transition tag tests
- Patch notes + known issues

---

## Tooling Leverage (Realistic)

### z3dk
- **Analyzer** prevents classic 65816 mistakes (width, ABI, return type).
- **Scaffold generator** prevents broken state routines and stack mismatches.
- **Hooks/annotations** keep tooling aligned with code intent.

### yaze / z3ed
- **Room inspection**: validate dungeon layouts, object placement, collision, and track alignment.
- **Dungeon maps**: batch generation to keep docs in sync with real ROM data.
- **Custom collision overlays**: expose problems early (minecart rails + stop tiles).

### Mesen2 + test runner
- **Automated transition checks** reduce regressions caused by small edits.
- **Known-good save states** provide reliable repro baselines.

---

## 2026 Full Release Scope (Realistic)

**Content goals:**
- All dungeons playable, including the final dungeon sequence.
- Narrative improvements completed (full text pass).
- Key gameplay additions finalized (minecart workflow, unique mechanics).
- Credits + epilogue complete.

**Tooling goals:**
- Stable dungeon editor workflow (selection, collision overlays, custom objects).
- Reliable lint + test pipeline for every beta patch.
- Clear documentation for dungeon maps and core systems.

---

## Open Risks
- ASM regressions from seemingly minor changes.
- Tooling inconsistencies (hook metadata vs real runtime state).
- Dungeon editor instability delaying design pass.

**Risk mitigation:**
- Strict lint + smoke on every risky change.
- Small, isolated commits with quick rollback.
- Use z3ed validation before editor-side design passes.

---

## Beta Patch Cadence (suggested)
- **Every 2-4 weeks** or at major milestones.
- Each patch should be playable and documented (no silent drops).
- Public testers get a stable path; experimental branches stay internal.
