# Sandbox and ROM Version Management Guide

**Purpose:** Run bug investigation, bisect, and regression testing in a **sandbox** separate from the main repo so you don’t make critical mistakes. Use a **dense local ROM library** in `Roms/` (never committed) and **scripts** for ROM version management and sandboxing (these are committed).

---

## Principles

1. **Sandbox** – Risky or comparative work (bisect, module isolation, trying fixes) happens in an isolated copy of the repo (git worktree). Main repo stays clean; you can discard the sandbox anytime.
2. **ROMs stay local** – All ROM binaries in `Roms/` are gitignored. Keep a dense set of old ROMs (pass/fail versions, bisect candidates) there; none are committed.
3. **Scripts are committed** – `scripts/rom_version_manage.py` and `scripts/sandbox_runner.sh` live in the repo and are the single way to manage ROM versions and sandbox lifecycle.
4. **Reproducible** – Same sandbox setup and same ROM selection produce the same test environment.

---

## What’s gitignored vs committed

| Location | Status | Notes |
|----------|--------|--------|
| `Roms/*.sfc`, `Roms/*.bst`, etc. | **Ignored** | ROM binaries and build artifacts; never commit. |
| `Roms/SaveStates/` | Partially ignored | Structure tracked; large `.mss`/`.srm` files ignored. |
| `Roms/versions.json` | **Ignored** | Optional catalog of ROM metadata (tags, pass/fail); local only. |
| `scripts/rom_version_manage.py` | **Committed** | ROM listing, tagging, selection, diff, run-test. |
| `scripts/sandbox_runner.sh` | **Committed** | Sandbox create / run / destroy. |

---

## 1. ROM version management

### 1.1 Where ROMs live

- Put all ROMs in **`Roms/`** (e.g. `oos168x.sfc`, `oos167x.sfc`, `oos166_pass.sfc`, `bisect_old.sfc`). The build script uses `Roms/oos<version>.sfc` or `Roms/oos<version>_test2.sfc` as base and writes `Roms/oos<version>x.sfc`.
- Keep “pass” and “fail” versions for the same scenario so you can diff or bisect (e.g. `oos168x.sfc` = current, `oos168x_pass_20260101.sfc` = known good backup).

### 1.2 Optional catalog: `Roms/versions.json`

The script can maintain a catalog at `Roms/versions.json` (created/updated by the script; gitignored). It maps ROM filenames to optional metadata:

- `label` – Human-readable name (e.g. "Known good overworld").
- `pass` – `true` / `false` for regression comparison.
- `note` – Short note (e.g. "Before time_system refactor").

You don’t have to use the catalog; listing and diff work from the filesystem alone.

### 1.3 Script: `rom_version_manage.py`

Run from repo root. All paths are relative to `Roms/` or the repo.

```bash
# List all ROMs in Roms/ (and catalog tags if present)
python3 scripts/rom_version_manage.py list

# Tag a ROM (writes/updates Roms/versions.json)
python3 scripts/rom_version_manage.py tag Roms/oos167x.sfc --label "Pre menu refactor" --pass

# Select a ROM for testing (prints path for use with OOS_BASE_ROM or run-test)
python3 scripts/rom_version_manage.py select oos167x
python3 scripts/rom_version_manage.py select --pass   # first ROM tagged pass=true

# Diff two ROMs (by name or path)
python3 scripts/rom_version_manage.py diff oos168x.sfc oos167x.sfc

# Run a test against a specific ROM (build with that base, then run bisect or regression)
python3 scripts/rom_version_manage.py run-test oos167x.sfc -- bisect
python3 scripts/rom_version_manage.py run-test --pass -- run_regression_tests.sh regression
```

**Environment:** `OOS_BASE_ROM` can override the base ROM used by `build_rom.sh`. `run-test` sets it for the child process so the chosen ROM is used as the base for that run.

---

## 2. Sandbox (reproducible isolated environment)

### 2.1 What the sandbox is

- A **git worktree** (separate checkout of the same repo at another path). You can run bisect, module isolation, or experimental builds there without touching the main working tree.
- The sandbox has its **own** working directory (e.g. `../oracle-of-secrets-sandbox`), so it has its own `Roms/` by default. To use your dense ROM set from the main repo, create the sandbox with **`--share-roms`**: the script will replace the sandbox’s `Roms/` with a symlink to the main repo’s `Roms/`, so both share the same ROM files.

### 2.2 Script: `sandbox_runner.sh`

```bash
# Create a sandbox (default: ../oracle-of-secrets-sandbox, or --name <name>)
# Use --share-roms to symlink Roms/ to the main repo so both use the same ROM set
./scripts/sandbox_runner.sh create [--name softlock-bisect] [--share-roms]

# Run a command inside the sandbox (from sandbox repo root)
./scripts/sandbox_runner.sh run [--name <name>] -- ./scripts/build_rom.sh 168
./scripts/sandbox_runner.sh run -- python3 scripts/bisect_softlock.py --frames 300
./scripts/sandbox_runner.sh run -- python3 scripts/repro_stack_corruption.py --strategy polling

# Destroy the sandbox (removes worktree; no effect on main repo or Roms/)
./scripts/sandbox_runner.sh destroy [--name <name>]
```

**Recommended flow:**

1. `sandbox_runner.sh create --name softlock-bisect --share-roms`
2. `sandbox_runner.sh run --name softlock-bisect -- git bisect start HEAD <good-commit>`
3. `sandbox_runner.sh run --name softlock-bisect -- git bisect run python3 scripts/bisect_softlock.py`
4. When done: `sandbox_runner.sh destroy --name softlock-bisect` (or leave it for more runs).

### 2.3 Reproducible sandbox for “pass” vs “fail” testing

- **Pass version:** Tag a known-good ROM with `rom_version_manage.py tag ... --pass` and/or keep it as e.g. `oos168x_pass.sfc`.
- **Sandbox + pass ROM:**  
  `sandbox_runner.sh run -- bash -c 'OOS_BASE_ROM=Roms/oos168x_pass.sfc ./scripts/build_rom.sh 168 && python3 scripts/bisect_softlock.py'`  
  Or use `rom_version_manage.py run-test --pass -- bisect` (or `run-test <fail_rom> -- run_regression_tests.sh regression`).
- **Same steps in sandbox each time** – Same worktree path, same ROM selection, same commands → reproducible environment.

---

## 3. Workflows

### 3.1 Bisect in sandbox without touching main repo

```bash
./scripts/sandbox_runner.sh create --name bisect-softlock
./scripts/sandbox_runner.sh run -- git bisect start HEAD <known-good-commit>
./scripts/sandbox_runner.sh run -- git bisect run python3 scripts/bisect_softlock.py
# Inspect result, then:
./scripts/sandbox_runner.sh destroy
```

### 3.2 Compare “pass” vs “fail” ROM with diff

```bash
python3 scripts/rom_version_manage.py tag Roms/oos167x.sfc --pass --label "Pre refactor"
python3 scripts/rom_version_manage.py diff oos168x.sfc oos167x.sfc
# Or: diff oos168x.sfc --pass
```

### 3.3 Run regression against an old “pass” ROM in sandbox

```bash
./scripts/sandbox_runner.sh create --name test-pass
./scripts/sandbox_runner.sh run -- python3 scripts/rom_version_manage.py run-test --pass -- run_regression_tests.sh regression
./scripts/sandbox_runner.sh destroy
```

### 3.4 Module isolation in sandbox

```bash
./scripts/sandbox_runner.sh create --name module-isolation
./scripts/sandbox_runner.sh run -- ./scripts/run_module_isolation.sh --auto
./scripts/sandbox_runner.sh destroy
```

---

## 4. Safety and hygiene

- **Never commit ROMs** – `.gitignore` already excludes `Roms/*` (except documented structure). Don’t force-add ROMs.
- **Sandbox is disposable** – `sandbox_runner.sh destroy` removes the worktree only; main repo and `Roms/` are unchanged.
- **Shared Roms/** – If you used `--share-roms` when creating the sandbox, its `Roms/` is a symlink to the main repo’s `Roms/`, so both use the same ROM files and catalog.
- **Backups** – For “pass” ROMs you care about, keep a copy outside the repo (e.g. `~/Archives/oos168x_pass_20260130.sfc`) if you want a permanent backup.

---

## 5. Related docs

- **Testing:** [README.md](README.md) – Regression suites, module isolation, bisect.
- **Root cause workflow:** [../Tooling/Root_Cause_Debugging_Workflow.md](../Tooling/Root_Cause_Debugging_Workflow.md).
- **Overworld/dungeon softlock approach:** [../Issues/OverworldDungeon_Softlock_Approach.md](../Issues/OverworldDungeon_Softlock_Approach.md).
- **Module isolation:** [../Issues/Module_Isolation_Plan.md](../Issues/Module_Isolation_Plan.md).
