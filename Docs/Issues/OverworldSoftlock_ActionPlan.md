# Overworld / Dungeon Black Screen — Action & Testing Plan
Date: 2026-01-28  
Owner (next): whoever picks up with mesen2-oos agent tooling

## Summary
- Symptom: intermittent overworld/dungeon load black screen and softlock (Save State 1 + 2).
- Current evidence points to stack/return corruption (invalid PC in bank $11, main loop not running).
- Recent patch attempts (P-state restore + long wrapper for HUD return) did **not** resolve the issue.

## Coordination / safety
- Do **not** attach to another agent’s live Mesen2 socket or pause their instance.
- Prefer an isolated Mesen2 home + socket and record the owner + socket in the run log.
- Confirm ROM CRC and base ROM path before every capture.

## Tooling sanity
- **Base ROM:** build from `Roms/oos168_test2.sfc` (ZScream OW v3). Emulator should load `Roms/oos168x.sfc` only.
- **Symbols:** prefer `scripts/export_symbols.py` output (`Roms/oos168x.mlb`). Avoid `labels-sync` while it imports non-ROM labels.
- **Evidence ledger:** detailed logs moved to AFS scratchpad  
  `~/.context/scratchpad/overworld_softlock_evidence_20260128.md`

## Primary capture targets
Capture both Save State 1 (pyramid overworld) and Save State 2 (menu hovered “New File” → dungeon load).

Minimum capture fields:
- Registers: `PC`, `K`, `DBR`, `S`, `P`
- Mode: `$7E0010` (GameMode), `$7E0011` (Submodule)
- Display: `$7E001A` (INIDISP), `$7E0013` (INIDISP queue)
- Room/entrance: `$7E00A0`, `$7E010E`
- Color math mirrors: `$9A/$9C/$9D`
- Stack + DP windows (always include)
- CPU0 trace ring (200–500 entries) around the failure

## Hypotheses to validate (ordered)
1) Stack corruption before `SpritePrep_LoadPalette` returns (corrupted return address → jump to data).
2) Hook bitness/DBR leakage in `time_system` or palette hooks (P not restored).
3) Overlay pointer corruption in `ZSCustomOverworld` (table value invalid for specific entrances).
4) JSL/RTL mismatch elsewhere in the transition path.

## Next steps (execute in order)
1) Reproduce Save State 1 + 2 with isolated socket and full stack/DP capture.
2) Set write watch on `$0100-$01FF` and break at `$0D:B870` to inspect the return bytes.
3) Break on `Module_MainRouting` / `MainGameLoop` to confirm whether the main loop ever resumes.
4) If stack corruption confirmed, diff stack content vs a known-good state to locate the clobber.
5) Only after baseline capture, toggle hooks (followers/water/torch) one at a time.

## References
- Evidence/log ledger: `~/.context/scratchpad/overworld_softlock_evidence_20260128.md`
- Checklist: `Docs/Issues/BuildingEntry_BlackScreen_Debug.md`
