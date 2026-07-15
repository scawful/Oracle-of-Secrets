# Scripts Index

This repo has accumulated scripts over time. The goal is to keep a small “golden path” and treat everything else as optional/internal.

## Golden Path
- Quick build + reload: `Scripts/Build/oos-quick.sh`
- Quick build + reload + validate: `Scripts/Build/oos-verify.sh`
- Named debug sessions: `Scripts/Build/oos-session.sh`
- Metadata popup control panel: `Scripts/Debug/oos_state_popup.py`
- Build loop: `Scripts/Build/dev_loop.sh`
- Build ROM directly: `Scripts/Build/build_rom.sh`
- Debug client (socket API): `Scripts/Mesen2/mesen2_client.py`
- Launch isolated Mesen2 instance: `Scripts/Mesen2/mesen2_launch_instance.sh`
- Run manifest-based tests: `Scripts/Validate/run_regression_tests.sh`
- Verify ROM overlap: `Scripts/Build/check_zscream_overlap.py`
- Package a beta patch: `Scripts/Build/beta_patch.sh`

## Common Debug Helpers
- Blackout capture bundle: `Scripts/Debug/capture_blackout.py`
- Transition repro helper: `Scripts/Debug/repro_blackout_transition.py`
- Module/feature flag editing:
  - `Scripts/Build/set_module_flags.py`
  - `Scripts/Build/set_feature_flags.py`

## Generation / Validation
- Hook metadata: `Scripts/Generate/generate_hooks_json.py`, `Scripts/Validate/verify_hooks_json.py`
- Hack manifest: `Scripts/Generate/generate_hack_manifest.py`
- Yaze project registry outputs (iOS/Mac Oracle dashboards): `Scripts/Analysis/extract_resource_labels.py` → `Docs/Dev/Planning/oracle_resource_labels.json`
- Yaze story events export (iOS/Mac Oracle dashboards): `Scripts/Analysis/extract_story_events.py` → `Docs/Dev/Planning/story_events.json`
- Symbol export: `Scripts/Generate/export_symbols.py`
- Docs lint: `Scripts/Analysis/lint_docs.py`
- Portable iOS/Mac project bundle: `Scripts/Generate/export_yazeproj_bundle.py --out-icloud` → `iCloud Drive/Yaze/Projects/*.yazeproj`

## Automation (Experimental / WIP)
- `Scripts/Campaign/` (agentic automation, autonomous debugging)

If a doc references a removed legacy CLI, prefer the socket client (`Scripts/Mesen2/mesen2_client.py`) instead.

## Save-State Safety Defaults
- `Scripts/Mesen2/mesen2_launch_instance.sh` does **not** seed project slot states by default.
- Opt-in legacy seeding only with `--seed-project-states`.
- `Scripts/Build/oos-session.sh` loads task seeds from `Docs/Debugging/Testing/trusted_state_seeds.json` and requires `canon + human-captured` states.
- Use `Scripts/set_trusted_state_seed.py <task> <state_id>` to map trusted library states to session tasks.
- Use `Scripts/Debug/oos_state_popup.py --instance <name> [--font-size 18] [--theme dark] [--layout compact]` for integrated metadata capture, macros, shortcuts, and custom test actions.
- Macro buttons/shortcuts are loaded from `Docs/Debugging/Testing/oos_ui_macros.json` so workflows can be edited without Python changes.
