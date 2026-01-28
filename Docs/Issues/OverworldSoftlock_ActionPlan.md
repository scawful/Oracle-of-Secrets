# Overworld / Dungeon Black Screen — Action & Testing Plan
Date: 2026-01-28  
Owner (next): whoever picks up with mesen2-oos agent tooling

## Summary
- Symptom: intermittent overworld/dungeon load black screen and softlock (Save State 1 + 2).
- Current evidence points to stack/return corruption (invalid PC in bank $11 / bank $1D, main loop not running).
- Recent patch attempts (P-state restore + long wrapper for HUD return) did **not** resolve the issue.

## New evidence (2026-01-28)
- SP page jump happens **before** NMI entry, not inside `NMI_PrepareSprites`.
- Logged SP jump: `TCS` at `PC=1D7324`/`PC=1D72D4` sets `SP=2727` (A=2727, DBR=50, D=02A4).
- JumpTableLocal called with X/Y **8-bit**:
  - `JSL ret=0684F3 to=008781` with `P=B0` (IndexMode8) → `PLY` pops 1 byte → stack misalignment.
  - Subsequent RTL returns to corrupted address (`83:A607`) and later JSL goes to `1D:66CC` (invalid).
- Invalid control flow captured: `JSL ret=83A670 to=1D66CC invalid=1`, followed by `Invalid PC prev=83A66D now=1D66CC` before the SP jump.
- NMI loop repeats, but main loop breakpoints (`Module_MainRouting`, `MainGameLoop`) never hit.
- Conclusion: corruption happens in mainline execution path; NMI loop is a symptom, not the root.

## Coordination / safety
- Do **not** attach to another agent’s live Mesen2 socket or pause their instance.
- Prefer an isolated Mesen2 home + socket and record the owner + socket in the run log.
- Confirm ROM CRC and base ROM path before every capture.

## Tooling sanity
- **Base ROM:** build from `Roms/oos168_test2.sfc` (ZScream OW v3). Emulator should load `Roms/oos168x.sfc` only.
- **Symbols:** prefer `scripts/export_symbols.py` output (`Roms/oos168x.mlb`). Avoid `labels-sync` while it imports non-ROM labels.
- **Evidence ledger:** detailed logs moved to AFS scratchpad  
  `~/.context/scratchpad/overworld_softlock_evidence_20260128.md`

Symbol sanity checks:
- If disassembly shows WRAM labels at `$00:00xx`, you are likely viewing WRAM; switch to ROM bank (e.g. `$00:8000`).
- Ensure `MESEN2_HOME` points at the correct profile before `scripts/export_symbols.py --sync`.
- If labels look wrong, clear labels and reload `Roms/oos168x.mlb` only.

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
2) Hook bitness/DBR leakage in `time_system` or palette hooks (P not restored, X left 8-bit).
3) Overlay pointer corruption in `ZSCustomOverworld` (table value invalid for specific entrances).
4) JSL/RTL mismatch elsewhere in the transition path.
5) Direct stack overwrite (`$0100-$01FF`) from a stray `STA $0100,X`-style write.

## Next steps (execute in order)
1) Reproduce Save State 1 + 2 with isolated socket and full stack/DP capture.
2) Break on `SpriteModule_Initialize` (`$06:864D`) and `SpriteModule_Active` (`$06:84E2`) and log `P` before each `JSL JumpTableLocal`.
3) Set write watch on `$0100-$01FF` and break at `$0D:B870` (SpritePrep_LoadPalette RTL) to inspect return bytes.
4) Use socket TRACE to capture 200–500 instructions around the first `JumpTableLocal` call where `P` shows X=8-bit.
5) If X-bit leak confirmed, trace back to the last `SEP #$10`/`REP #$10` or missing `PLP` in the call chain.
6) If stack overwrite confirmed, log the write PC and diff against a known-good state.
7) Only after baseline capture, toggle hooks (followers/water/torch) one at a time.
8) Break on `$83:A66D` (from invalid jump log) to inspect the JSL target address bytes and stack contents just before the `1D:66CC` jump.

## References
- Evidence/log ledger: `~/.context/projects/oracle-of-secrets/scratchpad/overworld_softlock_evidence_20260128.md`
- Checklist: `Docs/Issues/BuildingEntry_BlackScreen_Debug.md`
