# CODE RED: Save-State Workflow Failure (2026-02-14)

## Summary
Debug sessions were repeatedly started from `lib-load` library IDs instead of the active project save files in `Roms/SaveStates/oos168x/`.
This produced bad repro context and wasted debugging time.

## Impact
- Entrance/dungeon investigations started from wrong state sources.
- Agent workflow drifted away from user-owned runtime states.
- Debug conclusions became noisy because repro seeds were not trusted.

## Root Causes
- Runbook and launcher guidance over-emphasized `lib-load`.
- `mesen2_client.py load` positional argument accepted only `int`, so `load <path>` failed in argparse.
- Relative file paths for `load` were not normalized to absolute paths.
- `mesen2_client.py --instance <name>` could silently attach to a different live socket when `MESEN2_SOCKET_PATH` was stale from a prior invocation.

## Immediate Fixes Applied
- `mesen2_client.py load` now accepts positional `slot` **or** positional `path`.
- `load` now normalizes relative paths to absolute paths.
- `agent load` got the same slot/path fix.
- Added tests for slot/path resolution and path normalization.
- `mesen2_client.py --instance <name>` now clears stale `MESEN2_SOCKET_PATH`, resolves the instance through registry/expected socket path, and fails fast if unresolved.
- Mesen bridge instance->socket resolution is now lazy (runtime), not import-time, so CLI args/env are honored deterministically.
- Added regression tests for instance resolution/preflight behavior.
- `scripts/mesen2_launch_instance.sh` now seeds F-key slot states from `Roms/SaveStates/<rom-base>/` into each new isolated instance by default (opt-out: `--no-seed-project-states`).
- Updated `RUNBOOK.md` with CODE RED policy: default to `Roms/SaveStates/oos168x/*.mss`.
- Updated `scripts/mesen2_launch_instance.sh` messages to recommend `load <path>` instead of `lib-load`.

## Mandatory Policy (Effective Immediately)
- Default debug state source: `Roms/SaveStates/oos168x/*.mss`.
- Use `lib-load` only when explicitly requested for a named library seed.
- Any repro report must include the exact loaded state file path.
