# Handoff: Zora Entrance Blackout (Valid User Seed)

Date: 2026-02-14  
Owner handoff: next agent  
Status: FIXED (dark-room regression fixed 2026-02-15; entrance blackout no longer reproduces on current build)

Update 2026-02-22:
- Sections in this handoff that describe timeout-hook flag mitigations are historical investigation notes.
- Current source guidance is tracked in `Docs/STABILITY.md` and shared `.context` handoff/investigation files.

## Progress Update (2026-02-15)
- Rebuilt ROM from current workspace and validated fresh output:
  - ROM: `Roms/oos168x.sfc`
  - CRC32: `9A6CABF8`
  - SHA1: `C1FCE0298585252965EB7898B221333142E56F79`
- Reproduced entrance path on fresh isolated instance:
  - Instance: `oos-codex-zorafix-20260215`
  - Seed used: `/Users/scawful/Library/Application Support/Mesen2-instances/oos-codex-top-20260214/SaveStates/oos168x_2.mss`
- Result: previous entrance blackout did not reproduce.
  - Outside -> enter temple: stable (`mode=0x07`, room `0x28`) across 5/5 runs.
  - Indoors walk straight up to staircase and transition: stable to next room (`room=0x38`, submode returns to `0`).

Conclusion (as of 2026-02-15):
- The original “entering Zora Temple from outside blacks out” symptom appears resolved on current build.
- Active investigation moved to a new in-dungeon crash reported from updated slot-2 save (dark-room/layering room when moving left).

## Dark-Room LEFT Crash: Root Cause + Fix (2026-02-15)
New repro seed used for this follow-up:
- `/Users/scawful/Library/Application Support/Mesen2-instances/oos-codex-zorafix-20260215/SaveStates/oos168x_2.mss`

Deterministic repro (before fix):
- `press LEFT --frames 90`, then `run --frames 360`
- Result: `mode/sub/room -> 0x40`, PC executes WRAM/garbage (`$000D1C` class), stack corruption.

Root cause (confirmed):
- Vanilla bytes at room-load torch loop branch site are `D0 E8` at ROM offset `0x88E0` (`$01:88E0`).
- Patched ROM had `D0 C9`, which changes branch target to `$01:88AA` (mid-instruction `RTI`) instead of looping safely.
- This came from:
  - `Dungeons/dungeons.asm` (`Underworld_LoadRoom_ExitHook`) at `org $0188DF`.
  - `BNE $0188C9` assembled as low-byte literal (`C9`) in this context, not the intended relative offset.

Fix applied:
- `Dungeons/dungeons.asm`:
  - Replaced the unsafe assembled branch with explicit vanilla bytes:
  - `db $D0, $E8`
  - Kept `SEP #$30` as-is.

Validation after fix:
- Rebuilt ROM and loaded into `oos-codex-zorafix-20260215`.
- New ROM hash in runtime:
  - `SHA1: 9A9CAED6CE83...`
- Re-ran deterministic repro loop 5 times:
  - All 5/5 runs stable.
  - End state remains valid (`mode=0x07`, `sub=0`, `room=0x52`, indoors).

Evidence:
- `Docs/Debugging/Issues/evidence/zora_darkroom_left_crash_2026-02-15/p_log_8k.json`
- `Docs/Debugging/Issues/evidence/zora_darkroom_left_crash_2026-02-15/capture_20260215_113555/`

## Scope
- Focus only on the valid user-created state at Zora Temple exterior entrance.
- Investigate why entering the dungeon black-screens / corrupts game state.

## Hard Constraint From User
- Do **not** patch `LoadSongBank` during this handoff path.

## Canonical Repro Seed
- State path:
`/Users/scawful/Library/Application Support/Mesen2-instances/oos-codex-top-20260214/SaveStates/oos168x_2.mss`
- Visual validation: Link outside Zora Temple, directly in front of stairs/door.

## Repro (Confirmed)
Using isolated instance (`oos-codex-darkroom-20260214`):

```bash
cd /Users/scawful/src/hobby/oracle-of-secrets
MESEN2_INSTANCE=oos-codex-darkroom-20260214 python3 scripts/mesen2_client.py load "/Users/scawful/Library/Application Support/Mesen2-instances/oos-codex-top-20260214/SaveStates/oos168x_2.mss"
MESEN2_INSTANCE=oos-codex-darkroom-20260214 python3 scripts/mesen2_client.py press UP --frames 60
MESEN2_INSTANCE=oos-codex-darkroom-20260214 python3 scripts/mesen2_client.py run --frames 300
MESEN2_INSTANCE=oos-codex-darkroom-20260214 python3 scripts/mesen2_client.py diagnostics --json
```

Observed result:
- `mode=0x80`, black screen, invalid state.

Threshold behavior:
- `UP --frames 20`: does not enter, remains stable outside.
- `UP --frames 40` or higher: reproducible corruption/blackout.

## Diagnostic Signal
- If `0x7E0136` is pre-set to `0x01` before entering, transition succeeds into dungeon:

```bash
MESEN2_INSTANCE=oos-codex-darkroom-20260214 python3 scripts/mesen2_client.py load "/Users/scawful/Library/Application Support/Mesen2-instances/oos-codex-top-20260214/SaveStates/oos168x_2.mss"
MESEN2_INSTANCE=oos-codex-darkroom-20260214 python3 scripts/mesen2_client.py mem-write 0x7E0136 0x01
MESEN2_INSTANCE=oos-codex-darkroom-20260214 python3 scripts/mesen2_client.py press UP --frames 60
MESEN2_INSTANCE=oos-codex-darkroom-20260214 python3 scripts/mesen2_client.py run --frames 300
```

Observed result:
- `mode=0x07`, `room=0x28`, no blackout.

Interpretation:
- Failure is strongly coupled to the underworld song-bank transfer path.

## Evidence Bundle
- Directory:
`Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14`
- Key files:
`Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/oos168x_2.png`  
`Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/zora_slot2_manual_after.png`  
`Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/zora_slot2_manual_after.json`  
`Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/zora_slot2_entry_repro_20260214.json`  
`Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/zora_slot2_blame_mode.json`  
`Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/zora_slot2_trace_tail.json`

## Mesen2-OOS Workflow (Agent Quickstart)
1. Pick a single instance and stick to it.
```bash
python3 scripts/mesen2_registry.py status --refresh
```
2. Set explicit target.
```bash
export MESEN2_INSTANCE=oos-codex-darkroom-20260214
```
3. Health + baseline.
```bash
python3 scripts/mesen2_client.py health --json
python3 scripts/mesen2_client.py diagnostics --json
```
4. Load seed by absolute path (do not rely on library aliases).
```bash
python3 scripts/mesen2_client.py load "<absolute .mss path>"
```
5. Capture proof each run:
```bash
python3 scripts/mesen2_client.py screenshot --out /tmp/<name>.png
python3 scripts/mesen2_client.py diagnostics --json > /tmp/<name>.json
```
6. Memory instrumentation:
```bash
python3 scripts/mesen2_client.py mem-watch clear
python3 scripts/mesen2_client.py mem-watch add --depth 8000 0x7E0010
python3 scripts/mesen2_client.py mem-blame --addr 0x7E0010 --json
```

## Suggested Next Investigation (Without LoadSongBank Patches)
1. Break on `MODE` write and capture call path right before corruption (`0x7E0010` write to `0x80` / `0x49` phases).
2. Capture stack return chain right before invalid-mode write:
```bash
python3 scripts/mesen2_client.py stack-retaddr
```
3. Compare execution with and without forced `$0136=01` to isolate first divergent PC.
4. Keep this seed as canonical; do not switch to legacy or ambiguous library states.

## Follow-up Review (Codex, 2026-02-14)
### What the previous work got right
- Canonical seed and threshold repro are solid (`UP` 40+ fails, `UP` 20 stable).
- Control toggle `$7E0136=01` is the correct binary split and remains reproducible.

### Gap in prior evidence interpretation
- `mem-blame` entries like `pc=0x008002` (`BRK`) and repeated impossible writers were post-corruption artifacts, not root writers.
- Root-cause capture needed to happen before state corruption, not after `MODE=0x80`.

## New Findings (No LoadSongBank source patching performed)
- Confirmed on live instance `oos-codex-top-20260214` with the same seed.
- Failing path APU write sequence (`APUIO0`):
  - `0x029BFF` writes `0xFF`
  - `0x2CFC7F` writes `0xCC`
  - `0x2CFCA5` clears to `0x00` (timeout path)
- Forced-good path (`$7E0136=01`) never enters that transfer sequence.
- Step trace at timeout exit shows bank-return failure:
  - `PC 0x2CFCA8 -> ... -> 0x2CFCB2`
  - next step jumps to `0x2C8923` (wrong bank), then cascades through `0x00FFFF/0x008002`.
- Inference from trace + ROM bytes:
  - `LoadSongBank` is hooked via `JML` into bank `$2C`, but wrapper exits with `RTS`.
  - `RTS` keeps `K=$2C`, so it returns to bank-`$2C` using a return address intended for bank `$00`.
  - This explains invalid control flow and subsequent `MODE=0x80` corruption.

## Common-Sense Debugging Techniques (for transition/audio faults)
1. Validate live target first (`health`, `diagnostics`) and avoid stale sockets.
2. Always establish one-byte control split (here: `$7E0136=01`) before deep tracing.
3. Watch the smallest causal surface first (`APUIO0`, `SONGBANK`) before broad `MODE` traces.
4. Treat `BRK`/nonsense PC writers as artifact flags; move breakpoints earlier in time.
5. For cross-bank hooks, explicitly verify call/return semantics:
   - `JML` entry routines must not `RTS` unless they re-establish caller bank.
   - `JSL`/`RTL` and `JSR`/`RTS` pairing must remain coherent across hook boundaries.
6. Capture 8–12 single-step PC/SP snapshots around the suspected return instruction to prove control-flow corruption quickly.

## Additional Evidence (Codex Follow-up)
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/zora_slot2_apu_timeout_blame_20260214_codex.json`
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/zora_slot2_apu_timeout_diag_20260214_codex.json`
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/zora_slot2_apu_force0136_blame_20260214_codex.json`
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/zora_slot2_apu_force0136_diag_20260214_codex.json`
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/zora_slot2_apu_timeout_steptrace_20260214_codex.txt`

## Recent-Change Suspect Audit (Codex, 2026-02-14, Historical Notes)
This section captures archived local-branch debugging context and is not active-source guidance.
### High-confidence proximate culprit (local, uncommitted)
- `Core/patches.asm`: local `LoadSongBank_WithTimeout` hook (`org $008888 -> JML`) exits via `RTS` in bank `$2C`.
- `Config/feature_flags.asm` / `Util/macros.asm`: local `!ENABLE_APU_UPLOAD_TIMEOUT_GUARD = 1`.
- Result: deterministic wrong-bank return on timeout path, then invalid mode (`0x49/0x80` class corruption).

### Recent committed changes reviewed (indirect candidates)
- `d30fb96` (2026-02-07): hook-width hardening + follower transition changes.
- `43d08e3` (2026-02-08): water gate ABI hardening + scoped room-entry restore.
- `c39e3c7` (2026-01-30): ZoraBaby state width + long-addressing fixes.
- `08dc87a` (2026-02-06): ocarina song tint + Zora waterfall hint.

Assessment:
- None of the above committed changes modify `LoadSongBank`/`APUIO` handshake directly.
- The only direct `LoadSongBank` hook present in this tree is local/uncommitted.
- Commit history confirms prior SPC timeout hook was reverted on `2026-01-30` (`e258e88`).

## Focused A/B on "recent sprite work" hypothesis
Repro command family (seed + `UP` entry) still fails with invalid mode when sprite-adjacent features are disabled.

Key reports:
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/flag_probe_20260214_fast/baseline_up60_recheck.json`
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/flag_probe_20260214_fast/no_minecart_planned_track_table_up60.json`
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/flag_probe_20260214_fast/no_follower_hooks.json`
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/flag_probe_20260214_fast/no_graphics_transfer_hook.json`
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/flag_probe_20260214_fast/no_water_gate_hooks.json`
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/flag_probe_20260214_fast/no_custom_room_collision.json`
- `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/flag_probe_20260214_fast/no_transition_bundle.json`

Interpretation:
- Disabling recent sprite/transition suspects does not clear the anomaly signature.
- Disabling `apu_upload_timeout_guard` changes failure mode to legacy forced-blank/spin behavior, confirming the guard path is where current corruption is introduced.

## Experiment: Remove Timeout Guard (Codex, 2026-02-14, Historical Notes)
Goal:
- Remove active timeout-hook behavior and check whether entrance stabilizes.

Config tested:
1. `!ENABLE_APU_UPLOAD_TIMEOUT_GUARD = 0` only
   - Result: still fails (legacy hang signature).
   - Evidence: `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/flag_probe_20260214_fast/local_removed_apu_guard_up60.json`
   - Failure mode: `forced_blank` with `PC` in `LoadSongBank` sync wait region (`$0088EC/$0088EF`).

2. `!ENABLE_APU_UPLOAD_TIMEOUT_GUARD = 0` + `!ENABLE_EMERGENCY_SKIP_DUNGEON_SONGBANK_TRANSFER = 1`
   - Result: no anomaly detected in the repro window; outside->dungeon entry stays in valid mode path.
   - Evidence: `Docs/Debugging/Issues/evidence/zora_entrance_slot2_2026-02-14/flag_probe_20260214_fast/local_no_apu_guard_plus_emergency_skip_up60.json`

Practical takeaway:
- Removing timeout guard alone does **not** fix the entrance.
- Historical local workaround was to keep timeout guard off and enable emergency song-bank transfer skip.
