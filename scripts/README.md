# Scripts Index

This repo has accumulated scripts over time. The goal is to keep a small “golden path” and treat everything else as optional/internal.

## Golden Path
- Build ROM: `scripts/build_rom.sh`
- Debug client (socket API): `scripts/mesen2_client.py`
- Launch isolated Mesen2 instance: `scripts/mesen2_launch_instance.sh`
- Verify ROM overlap: `scripts/check_zscream_overlap.py`

## Common Debug Helpers
- Blackout capture bundle: `scripts/capture_blackout.py`
- Transition repro helper: `scripts/repro_blackout_transition.py`
- Module/feature flag editing:
  - `scripts/set_module_flags.py`
  - `scripts/set_feature_flags.py`

## Generation / Validation
- Hook metadata: `scripts/generate_hooks_json.py`, `scripts/verify_hooks_json.py`
- Hack manifest: `scripts/generate_hack_manifest.py`
- Symbol export: `scripts/export_symbols.py`
- Docs lint: `scripts/lint_docs.py`

## Automation (Experimental / WIP)
- `scripts/campaign/` (agentic automation, autonomous debugging)

If a doc references a script that does not exist (example: `mesen_cli.sh`), prefer the socket client (`scripts/mesen2_client.py`) instead.
