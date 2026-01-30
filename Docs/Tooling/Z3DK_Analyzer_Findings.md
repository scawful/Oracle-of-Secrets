# Z3DK Analyzer Findings (2026-01-29)

## Scope
- ROM analyzed: `Roms/oos168x.sfc` (patched)
- Symbols: `Roms/oos168x.sym`
- Hooks: `hooks.json` (generated from ASM org directives)
- Tools: `z3dk/scripts/oracle_analyzer.py` + `z3dk/scripts/oracle_validate.py`

## What was noisy / invalid (filters added)
- **Data pools and tables** were being treated as hook routines.
  - Examples: `Pool_*`, `RoomData*`, `Tile16`, `Map*`, `*Table`, `*Pointers`.
  - These caused false **ABI exit** warnings (no return states) and absurd push/pull imbalances.
- **Data labels in Oracle namespace** (`Oracle_pos1_x_low`, `Oracle_pos1_size`) were flagged as code targets.
- **Non-ROM targets** (e.g., WRAM labels) were being counted in JSL mismatch checks.

We added `skip_abi` + `module` to hooks.json and taught the analyzer to skip ABI checks
for data labels, anonymous patch hooks (`hook_XXXXXX`), `jmp/jml` hooks, and non-ROM targets.

Result after filters on `oos168x.sfc`:
- Diagnostics dropped from 1209 → 279
- ABI exit warnings dropped from 895 → 98
- M/X mismatch count dropped after skipping `long_entry` targets (now 181)

## Valid / likely real issues (post-filter focus)
These are likely genuine ABI risks and should be investigated in Oracle code:
- `Oracle_CustomRoomCollision` (caller `$01B95B`): **M flag mismatch**
- `Oracle_UseImplicitRegIndexedLocalJumpTable` (multiple call sites): **M/X mismatch**
- `Oracle_HUD_Update` (caller `$0DFB91` / `Oracle_newIgnoreItemBox`): **M mismatch**
- `Oracle_Graphics_Transfer` (caller `$02BE5E`): **X mismatch**
- `Oracle_UpdateGbcPalette` (caller `$07FA69` and others): **M/X mismatch**
- `Oracle_Overworld_DrawMap16_Persist` (several call sites in bank $34): **M/X mismatch**

## Potential investigation paths (filtered callsite mismatches)
- Oracle_Overworld_DrawMap16_Persist: 6 callsite mismatch(es); sample: $3489D5 (M flag mismatch, X flag mismatch), $3489DF (M flag mismatch, X flag mismatch), $3489E9 (M flag mismatch, X flag mismatch)
- Oracle_Link_HandleMovingAnimation_FullLongEntry: 5 callsite mismatch(es); sample: $028A44 (X flag mismatch), $0299C2 (X flag mismatch), $02C242 (X flag mismatch)
- Oracle_UpdateGbcPalette: 4 callsite mismatch(es); sample: $07FA69 (M flag mismatch, X flag mismatch), Oracle_ForceResetMask_GameOver_gbc_link (M flag mismatch, X flag mismatch), $3BF0C4 (M flag mismatch, X flag mismatch)
- Oracle_Sprite_DamageFlash_Long: 4 callsite mismatch(es); sample: Oracle_Sprite_Octorok_Move (X flag mismatch), Oracle_Sprite_WaterOctorok_Attack (X flag mismatch), Oracle_Sprite_Leever_Main (X flag mismatch)
- Oracle_Sparkle_PrepOAMFromRadial: 3 callsite mismatch(es); sample: $08D97A (M flag mismatch, X flag mismatch), $08DD6D (M flag mismatch), $2B867D (M flag mismatch, X flag mismatch)
- Oracle_Sprite_ProjectSpeedTowardsPlayer: 2 callsite mismatch(es); sample: $04EB91 (X flag mismatch), $1E8EA7 (X flag mismatch)
- Oracle_Ancilla_CheckDamageToSprite: 2 callsite mismatch(es); sample: $088309 (M flag mismatch), $088E60 (M flag mismatch)
- Oracle_Attract_SetUpConclusionHDMA: 2 callsite mismatch(es); sample: Oracle__0CF0DE (M flag mismatch), Oracle__0CF714 (M flag mismatch)
- Oracle_HUD_Update: 2 callsite mismatch(es); sample: $0DFB91 (M flag mismatch), Oracle_newIgnoreItemBox (M flag mismatch)
- Oracle_Sprite_ShowMessageMinimal: 2 callsite mismatch(es); sample: $1AFEF0 (X flag mismatch), $1DA4EC (X flag mismatch)
- Oracle_CustomRoomCollision: 1 callsite mismatch(es); sample: $01B95B (M flag mismatch)
- Oracle_Ancilla_SpawnFallingPrize: 1 callsite mismatch(es); sample: $01C742 (X flag mismatch)

## Validator findings
`oracle_validate.py` flagged:
- **Tile16 blank entries**: indices `0xEA4–0xEA7`
  - Likely tied to the bad copy into `oos168x.sfc` (see test ROM confusion).

## Next steps
1) Re-run analyzer after regenerating hooks.json (skip_abi/module in effect).
2) Inspect the ABI for the Oracle routines above (prolog/epilog M/X handling).
3) Confirm Tile16 data in `oos168x.sfc` vs `oos168x_test2.sfc` or backups.

See `Docs/Tooling/Oracle_ABI_Standard.md` for the new long-entry ABI convention
and macros (`OOS_LongEntry` / `OOS_LongExit`).
