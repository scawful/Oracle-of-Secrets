# Bug: Dark Room / Flashlight Overlay Entry Blackout

**Reported:** 2026-02-07
**Severity:** Critical
**Symptom:** Entering certain rooms with the dark-room effect causes a persistent black screen/softlock. The room is expected to show the "flashlight"/lamp cone overlay (and helper visuals), but instead the display stays black and play cannot continue.
**Status:** OPEN

## Working Hypotheses (What We Need To Confirm)

This class of blackout often comes from one of:
- **Brightness stuck at 0** (INIDISP low nibble `0x0`), not necessarily forced-blank (INIDISP bit7).
- **HDMA/windowing state** getting stuck or clobbered (spotlight/IRIS tables).
- **Hook ABI/DP leak** during room load (bad `REP/SEP` or nonzero `D`), causing vanilla dark-room setup code to misbehave.

Do not guess. Capture first.

## Capture Workflow (Fast)

1. Pause the emulator **one action away** from the doorway/stairs that enters the dark room.
2. Arm instrumentation:
```bash
python3 scripts/capture_blackout.py arm --save-seed --assert-jtl --deep
```
3. Reproduce the blackout (enter the room). Do **not** reset.
4. Capture:
```bash
python3 scripts/capture_blackout.py capture
```

Artifacts will be under `/tmp/oos_blackout/<timestamp>/`.

## What To Inspect In The Capture

Key values (all are watched by `--deep` now):
- `INIDISPQ` (`$7E0013`):
  - bit7 set => forced blank
  - low nibble `0x0` => brightness 0 (black without forced blank)
- `HDMAENQ` (`$7E009B`): stuck bits can indicate a windowing/spotlight HDMA issue.
- `DARKNESS` (`$7EC017`), `DARKLAMP` (`$7E0458`), `LIGHT` (`$7E045A`): expected to reflect dark-room state and lighting.
- `IRISTOP/IRISTYPE` (`$7E067C/$7E067E`): spotlight parameters.

Then use the blame files:
- `blame_inidispq.json`: who last wrote the display state?
- `blame_hdmaenq.json` (if present): who last changed HDMA enable?

## Repro Seed (TBD)

Add a state library seed once we have a stable repro:
- state id:
- entry action:
- expected vs actual:

