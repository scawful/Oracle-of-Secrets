# Scripts Index

This repo has accumulated scripts over time. The goal is to keep a small “golden path” and treat everything else as optional/internal.

## Golden Path
- Quick build + reload: `Scripts/Build/oos-quick.sh`
- Quick build + reload + validate: `Scripts/Build/oos-verify.sh`
- Named debug sessions: `Scripts/Build/oos-session.sh`
- Metadata popup control panel: `Scripts/Debug/oos_state_popup.py`
- Build loop: `Scripts/Build/dev_loop.sh`
- Build ROM directly: `Scripts/Build/build_rom.sh`
- Overlap check after ASM: `python3 Scripts/Build/check_zscream_overlap.py`
- Debug client (socket API): `Scripts/Mesen2/mesen2_client.py` (shim; the client lives in `../mesen2-oos/tools/oos_client`, override with `MESEN2_OOS_ROOT`)
- Launch isolated Mesen2 instance: `Scripts/Mesen2/mesen2_launch_instance.sh`
- Run manifest-based tests: `Scripts/Validate/run_regression_tests.sh regression`
- Test runner (socket backend): `Scripts/Validate/test_runner.py`
- Package a verified beta `.bps` + showcase `.srm` bundle: `Scripts/Build/beta_patch.sh` / `Scripts/Build/package_beta_bps.py`
- Generate the 3-slot beta showcase `.srm`: `Scripts/Build/generate_showcase_srm.py`
- 192-map overworld seam & arrival auditor: `Scripts/Build/check_overworld_seams.py`
- Stitched overworld diagnostic region board (with optional Yaze `--diff-rom`): `Scripts/Tools/overworld_region_board.py`
- Handheld (RG353P) testing: moved to the sibling repo `~/src/hobby/oos-rg353p`.

Older docs may still reference `./build.sh` or flat `scripts/…` paths. Prefer the Golden Path commands above.

## Common Debug Helpers
- Blackout capture bundle: `Scripts/Debug/capture_blackout.py`
- Transition repro helper: `Scripts/Debug/repro_blackout_transition.py`
- Module/feature flag editing:
  - `Scripts/Build/set_module_flags.py`
  - `Scripts/Build/set_feature_flags.py`

## Generation / Validation
- Hook metadata: `Scripts/Generate/generate_hooks_json.py`, `Scripts/Validate/verify_hooks_json.py`
- Hack manifest: `Scripts/Generate/generate_hack_manifest.py`
- Yaze project registry outputs: `Scripts/Generate/extract_resource_labels.py`, `Scripts/Generate/extract_overworld_registry.py`
- Room connectivity evidence report: `Scripts/Generate/extract_room_connectivity.py` (extracts grid adjacency candidates and raw header destinations; schema_version=2 evidence report, does not claim confirmed traversal or usable routes). Registry parsing and its report digest use the same captured bytes; file output uses an exclusively created temporary file and atomic replacement.
- Yaze story events export: `Scripts/Generate/extract_story_events.py`
- Symbol export: `Scripts/Generate/export_symbols.py`
- Portable iOS/Mac project bundle: `Scripts/Generate/export_yazeproj_bundle.py --out-icloud`

## Scope
Keep scripts here focused on building, generating, validating, packaging, or debugging the game.
Device deployment and external tooling live in their own repositories.

If a doc references a script that does not exist (example: `mesen_cli.sh`), prefer the socket client (`Scripts/Mesen2/mesen2_client.py`) instead.

## Save-State Safety Defaults
- `mesen2_launch_instance.sh` does **not** seed project slot states by default (`SEED_PROJECT_STATES=0`).
- Opt-in legacy seeding only with `--seed-project-states`.
- `oos-session.sh` loads task seeds from `Data/debug/trusted_state_seeds.json` and requires `canon + human-captured` states.
- Use `Scripts/set_trusted_state_seed.py <task> <state_id>` to map trusted library states to session tasks.
- Use `Scripts/Debug/oos_state_popup.py --instance <name> [--font-size 18] [--theme dark] [--layout compact]` for integrated metadata capture, macros, shortcuts, and custom test actions.
- Macro buttons/shortcuts are loaded from `Data/debug/oos_ui_macros.json` so workflows can be edited without Python changes.
