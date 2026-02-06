# Oracle of Secrets Campaign Log

This file is a lightweight, human-authored log for the autonomous campaign
tooling in `scripts/campaign/`.

If you need detailed run artifacts (reports, traces, screenshots, savestates),
write them to `/tmp` (or another scratch location) and avoid committing them.

## Optional Counters

These counters are parsed by some CLI commands. Keep them as plain integers.

**Overseer Agent:** 0
**Explorer Agent:** 0

## Optional Iteration Entries

If you want history/goals commands to show a timeline, add entries in this
format:

`## Iteration <N> (<agent>) - <title> (YYYY-MM-DD)`

Example:

`## Iteration 1 (overseer) - Establish baseline smoke run (2026-02-06)`
