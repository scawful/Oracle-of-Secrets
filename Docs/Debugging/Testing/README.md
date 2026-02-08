# Testing Infrastructure

Single reference for running and extending Oracle of Secrets tests.

## Quick start

```bash
# Smoke tests (fast; runs after build by default)
./scripts/run_regression_tests.sh smoke

# Regression suite (golden path, softlock checks, etc.)
./scripts/run_regression_tests.sh regression

# Quiet: one line per test
./scripts/run_regression_tests.sh regression -q
```

**Requires:** Mesen2 running with socket (single `/tmp/mesen2-*.sock` or `MESEN2_SOCKET_PATH`). Start with `./scripts/start_debug_session.sh` if needed.

## Entry points

| Command | Purpose |
|--------|---------|
| `./scripts/run_regression_tests.sh [suite]` | Run suites (thin wrapper → `test_runner.py`) |
| `python3 scripts/test_runner.py --suite smoke\|regression\|full` | Same; supports `--tag`, `-q`, `-v`, `--fail-fast` |
| `python3 scripts/test_runner.py tests/regression/golden_path_overworld.json` | Run one test file |
| `./scripts/run_module_isolation.sh --auto` | Module isolation (disable one module, build, run softlock test) |
| `python3 scripts/bisect_softlock.py` | Git bisect helper (build, load state 1, run N frames, good/bad) |

## Suites and tags

Defined in `tests/manifest.json`:

- **smoke** — Quick validation (boot, basic transition). Run on build.
- **regression** — Known-bug regression (Y overflow, mode reset, stack corruption, golden path overworld).
- **full** — All tests (smoke + regression).

Tags (run subset): `--tag golden_path`, `--tag critical`, `--tag overworld`, `--tag dungeon`.

Examples:

```bash
./scripts/run_regression_tests.sh regression --tag golden_path
python3 scripts/test_runner.py --suite regression --tag critical -q
```

## Options (run_regression_tests.sh / test_runner.py)

| Option | Effect |
|--------|--------|
| `-q`, `--quiet` | One line per test; no bridge/precondition/step output |
| `-v`, `--verbose` | Per-step and precondition detail |
| `--fail-fast` | Stop on first failure |
| `--moe`, `--no-moe` | MoE analysis on failure (default: on; set `OOS_MOE_ENABLED=0` to disable) |
| `--output-format json\|junit` | Machine-readable output |
| `--manifest PATH` | Override manifest (default: `tests/manifest.json`) |

## Module isolation and bisect

- **Module isolation:** Find which Oracle module is implicated in a softlock by disabling modules one at a time and running the softlock check.  
  `./scripts/run_module_isolation.sh --auto` (or manual `./scripts/run_module_isolation.sh` / `--next N`).  
  See `Docs/Debugging/Issues/Module_Isolation_Plan.md` and `Docs/Debugging/Issues/OverworldSoftlock_Plan.md` (Path C).

- **Git bisect:** Find the introducing commit.  
  `git bisect start HEAD <good-commit>` then `git bisect run python3 scripts/bisect_softlock.py`.  
  See `Docs/Debugging/Issues/OverworldSoftlock_Plan.md` (Path D).

## Test definitions

- Tests are JSON files under `tests/` (e.g. `tests/regression/golden_path_overworld.json`).
- Each has `name`, optional `saveState` (slot/path/id), and `steps` (wait, press, assert, screenshot, exec, etc.).
- Save state resolution: slot, path, or id from manifest/library. Default library root: `Roms/SaveStates/library` (see `tests/manifest.json` defaults and `Docs/Debugging/Testing/SaveStateLibrary.md`).

## Environment

| Variable | Purpose |
|----------|---------|
| `MESEN2_SOCKET_PATH` | Override Mesen2 socket path |
| `OOS_TEST_BACKEND` | Force backend: `socket` \| `yaze` \| `auto` |
| `OOS_MOE_ENABLED` | 1 = MoE on failure (default), 0 = off |

## Related docs

- **Sandbox and ROM versions:** [Sandbox_ROM_Guide.md](Sandbox_ROM_Guide.md) – Reproducible sandbox (git worktree), ROM version management (`rom_version_manage.py`), and safe bisect/isolation without touching the main repo.
- **Save states:** `Docs/Debugging/Testing/SaveStateLibrary.md`, `Docs/Debugging/Testing/save_state_library.json`
- **Overworld softlock:** `Docs/Debugging/Issues/OverworldSoftlock_Plan.md`, `Docs/Debugging/Issues/Module_Isolation_Plan.md`
- Historical gap-analysis docs live under `Docs/Archive/` (do not treat them as current guidance).
