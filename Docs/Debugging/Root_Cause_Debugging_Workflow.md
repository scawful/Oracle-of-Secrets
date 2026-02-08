# Root Cause Debugging Workflow (Current Golden Path)

This is the repeatable workflow for black screens, softlocks, transition hangs, and corruption in Oracle of Secrets.

If you only remember one place to start: `RUNBOOK.md` (repo root).

## 0) Setup (One-Time-ish)

- Vanilla truth: `~/src/hobby/usdasm` (addresses + expected register width/caller context).
- Runtime tooling: `python3 scripts/mesen2_client.py` (Mesen2 OOS fork socket API).
- Optional static analysis: `~/src/hobby/z3dk/scripts/oracle_analyzer.py`.

## 1) Preflight (Do This Before Any Investigation)

```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py run-state
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py diagnostics
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-verify-all
```

If preflight fails, stop and fix connectivity/symbols before chasing a bug.

## 2) Reproduce (Deterministic)

Prefer a **state library seed** rather than “walk there”:

```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py library
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-load <state_id>
```

If you need a “fresh but progressed” file for navigation speed, use save-data profiles/snapshots:

- See `Docs/Debugging/Fast_Travel_and_Test_Setups.md`.

## 3) Capture (Freeze The Crime Scene)

### Transition / dark-room / screen-blank issues

Use the automated capture bundle:

```bash
python3 scripts/capture_blackout.py arm --deep
# reproduce in-game (do NOT reset)
python3 scripts/capture_blackout.py capture
python3 scripts/capture_blackout.py summary
```

### Generic softlock / corruption

At the moment of failure:

```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py pause
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py cpu --json
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py stack-retaddr --json
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-save "failure snapshot" -t bug
```

## 4) Instrument (Find The Writer / Faulting PC)

The most useful primitives:

- `mem-watch` + `mem-blame` for “who wrote this address?”
- `p-watch` + `p-log` for M/X surprises across a short window
- `trace` / `trace-run` for instruction context around a PC
- `breakpoint` for precise halts

Example: screen blanking (INIDISPQ) and mode changes.

```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py mem-watch add 0x7E0013 --depth 256   # INIDISPQ
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py mem-watch add 0x7E0010 --depth 256   # GameMode
```

After repro, ask blame:

```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py mem-blame 0x7E0013 --json
```

## 5) Map PC -> Source

1. Resolve PC to symbol/file (preferred: symbols loaded + `symbols resolve`/`disasm`).
2. Verify caller expectations against `usdasm` before changing register width or stack behavior.

Useful commands:

```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py disasm --count 40
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py symbols resolve --addr 0x01ABCD
```

## 6) Document

For any bug worth fixing, leave a short issue doc with:

- Repro state id
- Repro steps (exact inputs if possible)
- Blame output (writer PC + instruction)
- Mapping to file/routine + why it is wrong in `usdasm` terms

Place it under `Docs/Debugging/Issues/` and keep it linkable from `RUNBOOK.md` if it becomes a common class of failure.

