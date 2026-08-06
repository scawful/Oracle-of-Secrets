# Debugging Tools Index (Golden Path)

This is a short index of the tools that are actually used today. For the step-by-step workflow, see:

- `Docs/RUNBOOK.md`
- `Docs/Debugging/Root_Cause_Debugging_Workflow.md`

## Primary Tools (Local, Supported)

### Build / Validate

- Default build loop: `Scripts/Build/dev_loop.sh 168 --mesen-sync --reload`
- Direct build script: `Scripts/Build/build_rom.sh 168`
- Verify overlap after build: `python3 Scripts/Build/check_zscream_overlap.py`
- Hook + sprite-table analysis (optional): `~/src/hobby/z3dk/scripts/oracle_analyzer.py --check-hooks --find-mx --check-sprite-tables`
- Beta patch packaging: `Scripts/Build/beta_patch.sh 168`

### Runtime Debugging (Mesen2 OOS fork socket API)

- CLI client: `python3 Scripts/Mesen2/mesen2_client.py`
- Launcher (isolated instance): `Scripts/Mesen2/mesen2_launch_instance.sh`
- Native in-window panel plan: `Docs/Debugging/Agent/Mesen2_OOS_Native_Debug_Panel_Plan.md`

Most used commands:

```bash
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug diagnostics
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug lib-save "repro seed" -t repro
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug lib-load <state_id>
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug mem-watch add 0x7E0013 --depth 256
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug mem-blame 0x7E0013 --json
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug trace-run --frames 2 --count 2000 --out /tmp/trace.jsonl
```

### Evidence Capture Bundles

- Blackouts (transition/dark-room): `Scripts/Debug/capture_blackout.py`

```bash
python3 Scripts/Debug/capture_blackout.py arm --deep
python3 Scripts/Debug/capture_blackout.py capture
python3 Scripts/Debug/capture_blackout.py summary
```

### Fast Navigation / Fresh Save Variables

- Save-data profiles, snapshots, `.srm` hot reload:
  - Doc: `Docs/Debugging/Fast_Travel_and_Test_Setups.md`
  - Command group: `python3 Scripts/Mesen2/mesen2_client.py save-data ...`

## Optional / External (Use When Needed)

- YAZE GUI / z3ed workflows:
  - This repo includes `Scripts/yaze_service.sh` to start/stop yaze server/GUI.
  - Keep Oracle docs independent of external YAZE AI helper scripts; those are not part of this repo’s supported debugging path.

- YAZE iOS/macOS project bundles (portable `.yazeproj` packages for iCloud Drive): `python3 Scripts/Generate/export_yazeproj_bundle.py --rom Roms/oos168.sfc --refresh-planning --force --out-icloud`

### Session Hygiene

- Prefer `--instance <name>` instead of loose auto-attach in multi-agent workflows.
- Audit instance clutter before long sessions: `python3 Scripts/Mesen2/mesen2_registry.py list`
- Prune dead registry entries carefully: `python3 Scripts/Mesen2/mesen2_registry.py prune --dry-run`
