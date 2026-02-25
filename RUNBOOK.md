# Oracle of Secrets Runbook (Build, Debug, Test)

This is the primary “how do I work on this repo” doc.

## Sources Of Truth
- Vanilla behavior + addresses: `~/src/hobby/usdasm` (the vanilla disassembly).
- Oracle code: this repo, rooted at `Oracle_main.asm`.
- Runtime inspection: Mesen2 OOS fork socket API via `python3 scripts/mesen2_client.py`.

## Build
Recommended:
```bash
mesen-agent build
python3 scripts/check_zscream_overlap.py
```

`scripts/build_rom.sh` now runs `z3ed oracle-menu-validate` by default as a
pre-build guard. Controls:
- `OOS_SKIP_MENU_VALIDATE=1` skips the check.
- `OOS_MENU_VALIDATE_STRICT=1` fails on warnings in addition to errors.
- `OOS_MENU_VALIDATE_FATAL=0` keeps failures non-fatal (not recommended).

Legacy:
```bash
./scripts/build_rom.sh 168
python3 scripts/check_zscream_overlap.py
```

## Yaze (Mac/iPad Project Bundles)
Refresh the Oracle dashboards (dungeons/overworld labels, story graph) used by yaze's Oracle project registry:
```bash
python3 scripts/extract_resource_labels.py
python3 scripts/extract_story_events.py
```

Export an iCloud-friendly `.yazeproj` bundle (openable on macOS and iOS yaze):
```bash
python3 scripts/export_yazeproj_bundle.py --rom Roms/oos168_test2.sfc --refresh-planning --force --out-icloud
```

## Launch + Attach
Recommended launcher:
```bash
mesen-agent launch oos
```

Isolated instance (useful when multiple sessions/agents exist):
```bash
./scripts/mesen2_launch_instance.sh --instance oos-you-debug --owner you --source manual
```

Attach CLI (pick one):
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py health
# or
MESEN2_SOCKET_PATH=/tmp/mesen2-....sock python3 scripts/mesen2_client.py health
```

## Preflight (Do This First When Debugging)
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py run-state
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py diagnostics
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-verify-all
```

## Save-State Workflow (CODE RED 2026-02-14)
Default policy: do **not** use library IDs for active debugging unless explicitly requested.
Use project save files in `Roms/SaveStates/oos168x/` first.

Launcher behavior:
- New isolated instances now seed F-key slot files from `Roms/SaveStates/<rom-base>/` into that instance's `SaveStates/` by default.
- Disable seeding with `scripts/mesen2_launch_instance.sh --no-seed-project-states` when you need a blank instance.

```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py load Roms/SaveStates/oos168x/oos168x_1.mss
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py load Roms/SaveStates/oos168x/oos168x_2.mss
```

Library usage is opt-in only:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py library
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-load <state_id>  # only when explicitly requested
```

`load <slot|path>` now accepts positional file paths and resolves relative paths to absolute paths.

## Save Variables: Profiles, Snapshots, `.srm` Hot Reload
Profiles (editable JSON loadouts):
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-list
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-apply zora_temple_debug
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-apply zora_temple_debug --no-persist
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-capture my_loadout --flags --only-nonzero
```

`profile-apply` now performs transactional apply by default (WRAM apply + readback verify + WRAMSAVE->SRAM persist + SRAM verify).
Use `--no-persist` for temporary WRAM-only testing.

Save-data snapshot library (WRAM savefile mirror `$7EF000-$7EF4FF`):
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data lib-save "zora temple pre-darkroom" -t zora-temple
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data lib-load <entry_id>
```

Cart SRAM (`.srm`) import/export + hot load:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data srm-dump /tmp/oos.srm
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data srm-load /tmp/oos.srm --hot
```

Persist patched WRAM save variables into cart SRAM without going through menus:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data repair-checksum
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data sync-to-sram
```

## Blackout / Softlock Evidence Capture
Transition/dark-room blackouts:
```bash
python3 scripts/capture_blackout.py arm --deep
# reproduce in-game (do not reset)
python3 scripts/capture_blackout.py capture
python3 scripts/capture_blackout.py summary
```

## Static Analysis (z3dk)
```bash
python3 ../z3dk/scripts/oracle_analyzer.py --check-hooks --find-mx --check-sprite-tables \
  --rom Roms/oos168x.sfc --hooks hooks.json
```

## Docs Lint (Keep Guidance Runnable)
```bash
python3 scripts/lint_docs.py
```

## Notes
- Prefer `mesen2_client.py` over legacy Lua/file-bridge stacks.
- When debugging “vanilla expectations” (register width, DP, stack), verify against `usdasm` first.
