# Dungeon Entrance Blackout Regression (Active Investigation)

Reported date: 2026-02-14  
Status: Investigating (D6 OW transition failure persists; historical APU mitigation experiments were removed from current source)  
Owner: codex

Update 2026-02-22:
- Timeout-hook and emergency-bypass flag experiments documented below are historical artifacts.
- Current source does not carry the timeout-hook mitigation path in `Core/patches.asm`.
- Use this file as evidence history, not as active implementation guidance.

## Scope
User reported a regression affecting entrance transitions (needed to validate D6 minecart work).

This note tracks verified evidence only.

## State Validity Protocol (Used in this investigation)
For each candidate seed:
1. Load source state.
2. Re-save under current ROM (`Roms/oos168x.sfc`) into repo library.
3. Reload saved state.
4. Compare key diagnostics fields (`mode`, `submode`, `area`, `room`, `indoors`, `link_x`, `link_y`, health/rupees).
5. Only accept seed if source/saved fields match.

This was done for both D6 seeds below.

## Verified Evidence

1. Legacy Zora seed context was validated (sanity baseline only):
- State ID: `zora_temple_stairs_seed_20260207`
- Confirmed dungeon context (`mode=0x07`, Zora Temple entrance)
- Artifact: `/tmp/oos_blackout_seed_zora_temple_stairs_seed_20260214.png`

2. Two D6 seeds were captured, re-saved under current ROM, and added to manifest:
- `pre_d6_entrance`  
  - Path: `Roms/SaveStates/library/oos168x/pre_d6_entrance.mss`  
  - MD5: `66c5039332a002b013963acd8ffb1a22`
- `inside_d6`  
  - Path: `Roms/SaveStates/library/oos168x/inside_d6.mss`  
  - MD5: `1df311f57ac628d2e026e2513e140f71`

3. Deterministic equivalence check passed for both seeds:
- Source vs re-saved diagnostics matched on all tracked key fields.
- Artifacts:
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/pre_d6_entrance_source_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/pre_d6_entrance_saved_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/inside_d6_source_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/inside_d6_saved_diag.json`

4. D6 OW entrance behavior from canonical `pre_d6_entrance`:
- `UP` (60/120 frames): remains `mode=0x09` (no dungeon transition).
- `RIGHT` and `UP+RIGHT`: enters `submode=0x06` with large X jumps (~+880) but still `mode=0x09`.
- This is treated as the current regression signal.
- Repro artifact after `RIGHT` hold:
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/pre_d6_right120.png`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/pre_d6_right120_diag.json`

5. Regression test wiring is now active (no silent skip):
- `tests/regression/transition_ow_d6.json` now uses `allowMissing: false` and **fails** reproducibly:
  - Failure: expected dungeon mode `0x07`, got `0x09`.
- `tests/regression/transition_d6_interroom.json` now uses `allowMissing: false` and **passes** on `inside_d6` after test-step fix.

6. Zora Temple entrance blackout from approved live state is reproducible and now instrumented:
- Seed used: `Roms/SaveStates/oos168x/zora_temple_outside_entry_approved_2026-02-14.mss`
- Baseline repro (`UP` 120f + run 240f):
  - Ends in `mode=0x07`, `submode=0x0F`, `area=0`, `room=0x28` with black screen.
  - CPU stalls at `$00:88EC/$00:88EF` (`LoadSongBank` sync wait loop: `CMP APUIO0` / `BNE`).
  - `APUIO0..3` readback at stall: `00 00 00 00`.
- Memory-write trail for transition path:
  - Entrance dispatch (Oracle hook namespace): writes `$010E=$25`, `$010C=$06`, `$10=$0F`, `$11=$00`.
  - Vanilla underworld load path: writes `$010C=$07`, `$10=$07`, `$11=$0F`.
  - APU transfer path:
    - `$029BFF` writes `$FF` to `APUIO0`.
    - `$0088E9` writes `$CC` to `APUIO0`.
    - CPU then waits forever at `$0088EC/$0088EF` for sync.
- Diagnostic bypass proving root path:
  - Pre-setting `$7E0136=01` before entering avoids the blackout and lands in `mode=0x07`, `submode=0x00`.
  - This bypass skips `Underworld_LoadSongBankIfNeeded` transfer, confirming the deadlock is in the song-bank transfer handshake path (not entrance table lookup/jump corruption).
- Artifacts:
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_black_baseline_songbank_hang.png`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_black_bypass_songbank_flag0136.png`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_black_apuio0_mem_blame.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_black_diag_apu_hang.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_bypass0136_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_black_baseline_cpu.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_bypass0136_cpu.txt`

7. Historical experiment (archived): emergency playtest unblock patch
- This section describes a past local experiment and is **not** current-source guidance.
- Flag added: `!ENABLE_EMERGENCY_SKIP_DUNGEON_SONGBANK_TRANSFER`
  - Default in `Util/macros.asm`: `0`
  - Current override in `Config/feature_flags.asm`: `0` (disabled after guard landed)
- Patch site:
  - `Overworld/ZSCustomOverworld.asm` adds `org $029BD7 : RTS` under the flag (underworld transfer bypass).
  - `Overworld/ZSCustomOverworld.asm` also bypasses OW-side transfer in `Overworld_LoadMusicIfNeeded` when `$0136 != 0`:
    - `STZ $0136`
    - `BRA .no_music_load_needed`
  - Runtime byte checks (from the emergency-enabled build used for A/B evidence):
    - `$029BD7 = $60` (`RTS`)
    - Active `Overworld_LoadMusicIfNeeded` entrypoint is `$0284D4` (callers now target `$84D4`), and bytes there matched the emergency branch path.
- Result from same approved Zora state and same input (`UP` 120f + run 240f):
  - Enters successfully with `mode=0x07`, `submode=0x00` (no blackout).
- Result for dungeon -> overworld from Zora Temple stairs seed:
  - At `DOWN` 120f + run 240f: transition is in progress (`mode=0x10`, `submode=0x01`), not hung.
  - At `DOWN` 120f + run 600f: settles to normal OW control (`mode=0x09`, `submode=0x00`, `indoors=0`) with no blackout.
- A/B check against no-emergency ROM (`oos168x_no_emergency_20260214.sfc`) remains failing:
  - Outside -> dungeon (`UP` 120f + run 240f): stalls at `PC $0088EC` (`mode=0x07`, `submode=0x0F`).
  - Dungeon -> outside (`DOWN` 120f + run 240f): stalls at `PC $0088EF` (`mode=0x08`, `submode=0x01`).
- Quick historical-candidate check (still no-emergency): disabling `FOLLOWER_TRANSITION_HOOKS` and `GRAPHICS_TRANSFER_SCROLL_HOOK` did **not** clear the stall.
  - Candidate build (`crc32=5D8913E7`) still stalls at `PC $0088EC/$0088EF` on the same two repro paths.
- Additional historical-candidate check (still no-emergency): disabling `WATER_GATE_HOOKS` and `WATER_GATE_OVERLAY_REDIRECT` did **not** clear the stall.
  - Candidate build (`crc32=AD69FA97`) still stalls at `PC $0088EF` on both repro paths.
- Artifacts:
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_emergency_patch.png`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_emergency_patch_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_emergency_patch_cpu.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_emergency_patch_byte.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_pre_ext_emergency_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_post_ext_emergency_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_post_ext_emergency_cpu.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_post_ext_emergency_pc.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_pre_ext_emergency.png`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_post_ext_emergency.png`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_pre_ext_emergency_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_post_ext_emergency_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_post600_ext_emergency_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_post_ext_emergency_cpu.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_post600_ext_emergency_cpu.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_post_ext_emergency_pc.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_post600_ext_emergency_pc.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_pre_ext_emergency.png`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_post_ext_emergency.png`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_post600_ext_emergency.png`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_no_emergency_post_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_no_emergency_post_pc.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_no_emergency_post_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_no_emergency_post_pc.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_candidate_disable_follower_graphics_no_emergency_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_candidate_disable_follower_graphics_no_emergency_pc.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_candidate_disable_follower_graphics_no_emergency_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_candidate_disable_follower_graphics_no_emergency_pc.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_candidate_disable_water_gate_no_emergency_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_outside_entry_candidate_disable_water_gate_no_emergency_pc.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_candidate_disable_water_gate_no_emergency_diag.json`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/zora_inside_exit_candidate_disable_water_gate_no_emergency_pc.txt`
- Caveat:
  - This bypasses dungeon song-bank transfer (music behavior may be wrong in affected transitions). It is intended only as a temporary stability unblock.

8. Historical experiment (archived): bounded APU handshake guard
- This section documents a removed mitigation path and is **not** current-source guidance.
- New flag: `!ENABLE_APU_UPLOAD_TIMEOUT_GUARD`
  - Default in `Util/macros.asm`: `1`
  - Active override in `Config/feature_flags.asm`: `1`
- Patch site:
  - `Core/patches.asm` now hooks `LoadSongBank` at `$008888` to `LoadSongBank_WithTimeout` in bank `$2C`.
  - Guard adds 16-bit timeout counters to APUIO polling loops (`$2140`) and exits cleanly on timeout instead of spinning forever.
- Verification with emergency bypass OFF:
  - `tests/regression/transition_zora_temple_roundtrip.json` passes (inside->outside->inside).
  - `scripts/repro_blackout_transition.py` reports `result=ok` for both directions:
    - `zora_inside_exit_apu_guard_report.json`
    - `zora_outside_entry_apu_guard_report.json`
  - No `$0088EC/$0088EF` spin signature observed in these guarded runs.

## Important Clarification
Earlier "no repro" statements applied only to the Zora seed and did not cover D6.

## Current Blockers
1. Root cause for `pre_d6_entrance` failing to transition (`0x09` persists, `submode 0x06` appears with X jump under rightward input).
2. Song-bank handshake hard lock root cause remains unknown (SPC non-ack path under investigation in current source).
3. Convert temporary findings into durable regression coverage for both Zora directions in CI-compatible state fixtures.

## Next Actions
1. Keep D6 OW instrumentation from `pre_d6_entrance` active:
- Track writes to `$7E0010`, `$7E0011`, `$7E010E`, and entrance dispatch path.
2. Treat timeout/emergency flag experiments as archived context only; do not use them as active validation profile guidance.
3. Audit song-bank producer path (`$0132/$0136` updates + transfer callers) to identify why SPC handshake occasionally fails to acknowledge.
4. Promote Zora roundtrip regression + repro-harness JSON reports as required checks for future transition/audio changes.

## Session Artifacts
- Evidence folder: `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/`
- Canonical seed screenshots:
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/pre_d6_entrance.png`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/inside_d6.png`
- Seed state summaries:
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/pre_d6_entrance_state.txt`
  - `Docs/Debugging/Issues/evidence/dungeon_entrance_blackout_2026-02-14/inside_d6_state.txt`
