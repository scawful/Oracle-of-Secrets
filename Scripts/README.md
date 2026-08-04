# Scripts Index

This repo has accumulated scripts over time. The goal is to keep a small “golden path” and treat everything else as optional/internal.

## Golden Path
- Quick build + reload: `Scripts/oos-quick.sh`
- Quick build + reload + validate: `Scripts/oos-verify.sh`
- Named debug sessions: `Scripts/Build/oos-session.sh`
- Metadata popup control panel: `Scripts/Debug/oos_state_popup.py`
- Build loop: `Scripts/dev_loop.sh`
- Build compatibility wrapper: `./build.sh`
- Build ROM directly: `Scripts/build_rom.sh`
- Debug client (socket API): `Scripts/Mesen2/mesen2_client.py`
- Launch isolated Mesen2 instance: `Scripts/Mesen2/mesen2_launch_instance.sh`
- Run manifest-based tests: `Scripts/Validate/run_regression_tests.sh`
- Verify ROM overlap: `Scripts/check_zscream_overlap.py`
- Package a beta patch: `Scripts/beta_patch.sh`

## Common Debug Helpers
- Blackout capture bundle: `Scripts/capture_blackout.py`
- Transition repro helper: `Scripts/repro_blackout_transition.py`
- Module/feature flag editing:
  - `Scripts/set_module_flags.py`
  - `Scripts/set_feature_flags.py`

## Generation / Validation
- Hook metadata: `Scripts/generate_hooks_json.py`, `Scripts/verify_hooks_json.py`
- Hack manifest: `Scripts/generate_hack_manifest.py`
- Yaze project registry outputs (iOS/Mac Oracle dashboards): `Scripts/extract_resource_labels.py` → `Docs/Dev/Planning/oracle_resource_labels.json`
- Yaze story events export (iOS/Mac Oracle dashboards): `Scripts/extract_story_events.py` → `Docs/Dev/Planning/story_events.json`
- Symbol export: `Scripts/export_symbols.py`
- Docs lint: `Scripts/lint_docs.py`
- Portable iOS/Mac project bundle: `Scripts/export_yazeproj_bundle.py --out-icloud` → `iCloud Drive/Yaze/Projects/*.yazeproj`

## Automation (Experimental / WIP)
- `Scripts/campaign/` (agentic automation, autonomous debugging)

If a doc references a script that does not exist (example: `mesen_cli.sh`), prefer the socket client (`Scripts/Mesen2/mesen2_client.py`) instead.

## Save-State Safety Defaults
- `mesen2_launch_instance.sh` does **not** seed project slot states by default.
- Opt-in legacy seeding only with `--seed-project-states`.
- `oos-session.sh` loads task seeds from `Docs/Debugging/Testing/trusted_state_seeds.json` and requires `canon + human-captured` states.
- Use `Scripts/set_trusted_state_seed.py <task> <state_id>` to map trusted library states to session tasks.
- Use `Scripts/Debug/oos_state_popup.py --instance <name> [--font-size 18] [--theme dark] [--layout compact]` for integrated metadata capture, macros, shortcuts, and custom test actions.
- Macro buttons/shortcuts are loaded from `Docs/Debugging/Testing/oos_ui_macros.json` so workflows can be edited without Python changes.
