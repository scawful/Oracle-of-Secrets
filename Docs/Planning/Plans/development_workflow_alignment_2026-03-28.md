# Oracle of Secrets - Development Workflow Alignment

**Date:** 2026-03-28
**Status:** Active planning
**Purpose:** Align next work, validation, and tooling around the repo's actual
current state instead of older roadmap assumptions.

---

## Executive Summary

Oracle of Secrets is no longer blocked by lack of tooling. The repo already has:

- A guarded build pipeline in `Scripts/Build/build_rom.sh`
- A one-command loop in `Scripts/Build/dev_loop.sh`
- A large Mesen2 socket client in `Scripts/Mesen2/mesen2_client.py`
- Save-data profiles and save-state library manifests
- JSON regression suites in `Tests/`
- yaze service helpers and portable `.yazeproj` export

The real bottlenecks now are:

1. Runtime validation debt
2. Save-state / save-data seed coverage gaps
3. Tooling and docs drift
4. Distribution workflow drift

That means the next work should prioritize confidence and workflow alignment
before large new feature pushes.

---

## Observed Repo Reality

### Working infrastructure already present

- `Scripts/Build/build_rom.sh` now does more than assembly:
  - menu validation
  - tracked water-table consumption on normal builds; generation only during an
    explicit opt-in refresh
  - `check_zscream_overlap.py`
  - hooks.json regeneration
  - optional sprite/hook validation
  - static analysis
  - smoke-test invocation when an emulator backend exists
  - GM-005 guard against accidentally editing `oos168x.sfc`
- `Scripts/Build/dev_loop.sh` wraps build, reload, symbol sync, validation, yaze
  restart, and yaze sync.
- `Scripts/Mesen2/mesen2_client.py` already supports:
  - save/load
  - save-data profiles
  - save-data snapshot library
  - SRAM import/export
  - traces, breakpoints, mem-watch, mem-blame
  - assistant mode
  - labels/symbol sync
- `Scripts/Mesen2/mesen2_launch_instance.sh` supports isolated instances, seeded save
  slots, registry-friendly instance naming, and safe profile separation.
- `Scripts/Generate/export_yazeproj_bundle.py` already supports portable macOS/iOS yaze
  bundles via `.yazeproj`.

### Concrete drift and friction points

- `mesen-agent` is referenced in docs, but is not on `PATH` here.
- `z3ed` is available at `~/src/hobby/yaze/build/bin/z3ed`.
- `yaze-nightly` is available on `PATH`.
- `/Applications/Mesen2 OOS.app` exists.
- `Scripts/yaze_service.sh status` shows yaze server and GUI are currently
  stopped.
- `PROJECT.toml` now points to a root `./build.sh` compatibility wrapper, but
  docs still need to keep `Scripts/Build/dev_loop.sh` as the primary path.
- `PROJECT.toml` declares `flips`, but `flips` is not on `PATH`.
- Distribution policy expects BPS patches, and `Scripts/Build/beta_patch.sh` now
  provides the repo path for that, but it still depends on `flips` being
  installed locally.
- `Scripts/Mesen2/mesen2_registry.py list` shows heavy historical instance clutter,
  which increases the chance of attaching to stale or ambiguous sessions.

---

## Current Priority Queue

### Priority 0 - Confidence before new content

1. **Create a canonical fast-test seed set**
   - Add or verify seeds for:
   - Maku Tree at 0/1/3/5/7 crystals
   - D4 waterfall / Zora Temple entry
   - D4 water-gate filled and unfilled room states
   - D6 overworld entrance
   - D6 inter-room minecart rooms
   - follower transition cases
   - menu stress case
2. **Promote transition and progression tests to daily-driver status**
   - Treat `transition_zora_temple_roundtrip.json`
   - Treat `transition_ow_d6.json`
   - Treat `transition_d6_interroom.json`
   - Treat Maku/progression checks as "run before new dungeon work"
3. **Runtime validate the assembled-but-untested systems already in tree**
   - `Core/progression.asm`
   - Maku Tree hint cascade
   - imported expanded dialogue paths
   - water-gate hooks
   - follower transitions

### Priority 1 - Resolve blockers that stop broader testing

1. **APU song-bank deadlock**
   - Still the top runtime blocker for Zora Temple and broader dungeon testing.
   - Keep investigation grounded in current source, not removed timeout-hook
     experiments.
2. **D6 overworld entrance failure**
   - Treat as a parallel blocker with a dedicated seed and compare path against a
     known-good dungeon entrance.
3. **Registry / instance hygiene**
   - Reduce attach ambiguity before more automated testing is added.

### Priority 2 - Only then push forward on feature/content work

1. D4 water-gate validation and room-entry restore
2. D6 minecart room completion and validation
3. Zora NPC conversion onto progression helpers
4. D7 rescue pipeline enable/test
5. Dialogue authoring / encoding passes that depend on validated runtime hooks

---

## Recommended Next Work Sessions

### Session A - Testing surface hardening

**Goal:** Make fast validation cheap and repeatable.

- Capture or verify the seed set listed above.
- Add missing save-data profiles:
  - `maku_tree_debug`
  - `menu_stress`
  - `d4_water_gate_debug`
  - `d6_minecart_debug`
- Verify canon entries in `Docs/Debugging/Testing/save_state_library.json`.
- Decide a small "must-run" subset:
  - build
  - smoke
  - transition tag tests
  - one manual spot-check for touched system

### Session B - Progression and hint runtime validation

**Goal:** Retire the highest-value "complete, untested" debt.

- Validate `GetCrystalCount`, `UpdateMapIcon`, and `SelectReactionMessage`
  through Maku Tree scenarios.
- Verify imported dialogue on key NPC routes:
  - Windmill Guy
  - Goron Elder
  - River Zora Elder
  - Bean Vendor
  - Cartographer
  - Koroks

### Session C - Dungeon blocker pass

**Goal:** Unblock D4/D6 testing.

- Reproduce and instrument the APU deadlock.
- Reproduce and instrument the D6 entrance failure.
- Promote any confirmed fixes immediately into regression coverage.

### Session D - Content work only after Sessions A-C

- D4 room audit and water-fill persistence
- D6 minecart placements and invariants
- Zora/Farore content wiring

---

## Validation Matrix

| Area | Minimum validation | Strong validation | Notes |
|------|--------------------|-------------------|-------|
| ASM hooks / core logic | `Scripts/Build/build_rom.sh 168` + overlap + analyzer | smoke + targeted regression JSON + manual Mesen repro | Use strict analyzer for beta drops |
| Dungeon room edits in yaze | `z3ed rom-compare` + `dungeon-doctor` + `rom-doctor` | rebuild + enter edited rooms + adjacent-room regression | Never edit `oos168x.sfc` |
| Progression/dialogue | save-data profile apply + targeted talk/interact test | state-backed regression steps + manual text review | Prefer save-data over long navigation |
| Overworld/dungeon transitions | smoke + transition JSON tests | isolated Mesen instance + trace / capture bundle | Promote failures into `Tests/regression/` |
| Beta patch candidate | smoke + transition tests + analyzer | full regression + curated manual play session | Do not ship without notes + known issues |

---

## Workflow Improvements Worth Doing Soon

### 1. Make `Scripts/Build/dev_loop.sh` the documented default

Current docs still split attention between `mesen-agent`, `build_rom.sh`, and
older workflow language. The practical default should be:

```bash
Scripts/Build/dev_loop.sh 168 --mesen-sync --reload
```

And for heavier validation:

```bash
Scripts/Build/dev_loop.sh 168 --mesen-sync --reload --validate
```

### 2. Pick one Mesen2 targeting rule and enforce it

Preferred rule:

- Launch with `Scripts/Mesen2/mesen2_launch_instance.sh --instance <name>`
- Attach with `--instance <name>`
- Avoid raw auto-attach whenever multiple sockets exist

This reduces accidental cross-session reuse and makes agent work safer.

### 3. Prune and separate stale registry state

The registry is too noisy. Add a regular cleanup habit:

- `python3 Scripts/Mesen2/mesen2_registry.py prune --dry-run`
- then prune for real after confirming no live work depends on those entries

Also keep instance naming short and task-specific:

- `oos-<owner>-<task>-<date>`

### 4. Expand save-data profiles before expanding automation

Right now only three built-in profiles exist:

- `soaring_debug`
- `zora_temple_debug`
- `all_items_no_progress`

That is not enough for the current validation backlog. More targeted profiles
will save more time than deeper campaign automation in the short term.

### 5. Split "golden path" from experimental automation

Use these as the real supported path:

- `Scripts/Build/build_rom.sh`
- `Scripts/Build/dev_loop.sh`
- `Scripts/Mesen2/mesen2_launch_instance.sh`
- `Scripts/Mesen2/mesen2_client.py`
- `Scripts/Validate/run_regression_tests.sh`
- `Scripts/Generate/export_yazeproj_bundle.py`
- `Scripts/yaze_service.sh`

Treat these as experimental until they prove consistent value:

- `Scripts/Campaign/`
- autonomous debugger flows
- higher-order agent gateway flows

### 6. Use the beta patch packaging path

The repo now has a BPS packaging path:

```bash
Scripts/Build/beta_patch.sh 168
```

Responsibilities:

- build patched ROM
- verify overlap + analyzer + required tests
- create BPS patch when `flips` exists
- emit versioned checksums
- write release notes stub / known issues stub

### 7. Keep portable testing first-class

The repo already supports portable yaze bundles:

```bash
python3 Scripts/Generate/export_yazeproj_bundle.py --refresh-planning --force --out-icloud
```

Use that for Mac/iPad room-data and planning sync. For portable emulator
testing, standardize on:

- patched ROM `Roms/oos168x.sfc`
- companion `.srm` exported via `save-data srm-dump`
- optional save-state pack copied from `Roms/SaveStates/oos168x/`

---

## Project Management Recommendations

Current oracle task tracking is content-heavy, but the immediate critical path
is testing/tooling-heavy. Recommended working buckets:

### Bucket A - Release blockers

- APU song-bank deadlock
- D6 overworld entrance failure
- regression confidence pass over AI-generated / untested changes

### Bucket B - Validation debt

- progression helper runtime validation
- Maku hint validation
- water-gate validation
- imported dialogue runtime validation
- menu / rain / L-R / ice / follower regression passes

### Bucket C - Workflow acceleration

- save-data profile expansion
- seed library cleanup and canonization
- Mesen2 registry prune discipline
- doc/tooling alignment
- beta patch packaging

### Bucket D - Content implementation

- D4/D6 authoring
- D7 rescue
- NPC progression conversions
- dialogue batch authoring / encoding

If oracle.org is updated, add explicit tasks for Bucket B and Bucket C so
testing debt is visible beside content work.

---

## Immediate Recommended Commands

### Build + validate

```bash
Scripts/Build/dev_loop.sh 168 --mesen-sync --reload --validate
```

### Launch isolated runtime session

```bash
Scripts/Mesen2/mesen2_launch_instance.sh --instance oos-scawful-debug --owner scawful --source manual
```

### Apply fast-travel state

```bash
python3 Scripts/Mesen2/mesen2_client.py --instance oos-scawful-debug save-data profile-apply zora_temple_debug
```

### Run daily regression subset

```bash
Scripts/Validate/run_regression_tests.sh smoke --no-moe --fail-fast
Scripts/Validate/run_regression_tests.sh regression --tag transition -q
```

### Export portable yaze bundle

```bash
python3 Scripts/Generate/export_yazeproj_bundle.py --refresh-planning --force --out-icloud
```

---

## Definition Of "Good Next Week"

This plan is succeeding if, by the next review:

- Maku Tree and progression helpers are runtime-validated
- D4 and D6 each have reliable canon repro seeds
- transition regressions are cheap to run
- docs no longer point to missing build commands
- beta patch packaging has a clear path instead of hand assembly

Until those are true, more content work should be selective rather than broad.
