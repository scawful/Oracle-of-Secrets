# Oracle of Secrets Runbook (Build, Debug, Test)

This is the primary “how do I work on this repo” doc.

## Sources Of Truth
- Vanilla behavior + addresses: `~/src/hobby/usdasm` (the vanilla disassembly).
- Oracle code: this repo, rooted at `Oracle_main.asm`.
- Runtime inspection: Mesen2 OOS fork socket API via `python3 Scripts/Mesen2/mesen2_client.py`.

## Build
Recommended:
```bash
Scripts/Build/oos-quick.sh
```

Safe z3dk smoke build (copies the base ROM into a temp workspace first and
never overwrites `Roms/oos168x.sfc`):
```bash
Scripts/Build/z3dk_safe_smoke.sh
```

Heavier verification pass:
```bash
Scripts/Build/oos-verify.sh
```

Underlying build loop:
```bash
Scripts/Build/dev_loop.sh 168 --mesen-sync --reload
```

`Scripts/Build/build_rom.sh` now runs `z3ed oracle-menu-validate` by default as a
pre-build guard. Controls:
- `OOS_SKIP_MENU_VALIDATE=1` skips the check.
- `OOS_MENU_VALIDATE_STRICT=1` fails on warnings in addition to errors.
- `OOS_MENU_VALIDATE_FATAL=0` keeps failures non-fatal (not recommended).

Legacy:
```bash
./build.sh 168
python3 Scripts/Build/check_zscream_overlap.py

# direct build script
./Scripts/Build/build_rom.sh 168
python3 Scripts/Build/check_zscream_overlap.py
```

## Yaze (Mac/iPad Project Bundles)
Refresh the Oracle dashboards (dungeons/overworld labels, story graph) used by yaze's Oracle project registry:
```bash
python3 Scripts/Analysis/extract_resource_labels.py
python3 Scripts/Analysis/extract_story_events.py
```

Export an iCloud-friendly `.yazeproj` bundle (openable on macOS and iOS yaze):
```bash
python3 Scripts/Generate/export_yazeproj_bundle.py --rom Roms/oos168.sfc --refresh-planning --force --out-icloud
```

The checked-in Oracle project and exported bundles are expected to open the
editable base ROM (`oos168.sfc` / bundle `rom`). Builds still produce and test
the patched output ROM (`oos168x.sfc`).

## Launch + Attach
ADHD-friendly session wrappers:
```bash
Scripts/Build/oos-session.sh maku --crystals 3
Scripts/Build/oos-session.sh d4
Scripts/Build/oos-session.sh d6
Scripts/Build/oos-session.sh menu
```

Recommended launcher:
```bash
./Scripts/Mesen2/mesen2_launch_instance.sh --instance oos-you-debug --owner you --source manual
```

Optional shortcut if you have local wrappers installed:
```bash
mesen-agent launch oos
```

Attach CLI (pick one):
```bash
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug health
# fallback
MESEN2_SOCKET_PATH=/tmp/mesen2-....sock python3 Scripts/Mesen2/mesen2_client.py health
```

## Preflight (Do This First When Debugging)
```bash
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug run-state
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug diagnostics
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug lib-verify-all
```

## Save-State Workflow (CODE RED 2026-02-14)
Default policy: do **not** use library IDs for active debugging unless explicitly requested.
Use project save files in `Roms/SaveStates/oos168x/` first.

Launcher behavior:
- New isolated instances now seed F-key slot files from `Roms/SaveStates/<rom-base>/` into that instance's `SaveStates/` by default.
- Disable seeding with `Scripts/Mesen2/mesen2_launch_instance.sh --no-seed-project-states` when you need a blank instance.

```bash
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug load Roms/SaveStates/oos168x/oos168x_1.mss
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug load Roms/SaveStates/oos168x/oos168x_2.mss
```

Library usage is opt-in only:
```bash
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug library
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug lib-load <state_id>  # only when explicitly requested
```

`load <slot|path>` now accepts positional file paths and resolves relative paths to absolute paths.

## Save Variables: Profiles, Snapshots, `.srm` Hot Reload
Profiles (editable JSON loadouts):
```bash
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug save-data profile-list
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug save-data profile-apply zora_temple_debug
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug save-data profile-apply zora_temple_debug --no-persist
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug save-data profile-capture my_loadout --flags --only-nonzero
```

`profile-apply` now performs transactional apply by default (WRAM apply + readback verify + WRAMSAVE->SRAM persist + SRAM verify).
Use `--no-persist` for temporary WRAM-only testing.

Save-data snapshot library (WRAM savefile mirror `$7EF000-$7EF4FF`):
```bash
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug save-data lib-save "zora temple pre-darkroom" -t zora-temple
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug save-data lib-load <entry_id>
```

Cart SRAM (`.srm`) import/export + hot load:
```bash
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug save-data srm-dump /tmp/oos.srm
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug save-data srm-load /tmp/oos.srm --hot
```

Persist patched WRAM save variables into cart SRAM without going through menus:
```bash
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug save-data repair-checksum
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug save-data sync-to-sram
```

## Blackout / Softlock Evidence Capture
Transition/dark-room blackouts:
```bash
python3 Scripts/Debug/capture_blackout.py arm --deep
# reproduce in-game (do not reset)
python3 Scripts/Debug/capture_blackout.py capture
python3 Scripts/Debug/capture_blackout.py summary
```

## Static Analysis (z3dk)
```bash
python3 ../z3dk/scripts/oracle_analyzer.py --check-hooks --find-mx --check-sprite-tables \
  --rom Roms/oos168x.sfc --hooks Roms/hooks.json
```

## Docs Lint (Keep Guidance Runnable)
```bash
python3 Scripts/Analysis/lint_docs.py
```

## Beta Patch Packaging
```bash
Scripts/Build/beta_patch.sh 168
```

If `flips` is not installed, the script exits with a clear error instead of
producing a half-finished tester drop.

## Notes
- Prefer `mesen2_client.py` over legacy Lua/file-bridge stacks.
- Prefer `--instance <name>` over loose auto-attach when multiple sockets may exist.
- When debugging “vanilla expectations” (register width, DP, stack), verify against `usdasm` first.
