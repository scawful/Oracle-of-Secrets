# Agent Workflow (Lean)

Use this file only when the one-page `Docs/Agent/Quickstart.md` is not enough. The goal is to keep every agent on the same minimal path.

## Core stack (preferred)
- Emulator: `/Applications/Mesen2 OOS.app` (fork with socket auto-start).
- Client: `python3 scripts/mesen2_client.py` (auto-attaches only if a single socket exists; otherwise set `MESEN2_SOCKET_PATH` or use `--socket`/`--instance`).
- Build: `./scripts/build_rom.sh 168` (or version from ROM name).
- States: `scripts/state_library.py` + `lib-verify-all` guardrail.

## Five commands you actually need
```
python3 scripts/mesen2_client.py run-state
python3 scripts/mesen2_client.py diagnostics --json
python3 scripts/mesen2_client.py smart-save 5 --label "<bug>"
python3 scripts/mesen2_client.py lib-save "<bug>"
python3 scripts/mesen2_client.py watch --profile overworld
```
Other quick hits: `press`, `move`, `state-diff`, `labels-sync`, `capture --json`.

## Baseline loop (GUI)
1. Build ROM; open in Mesen2 (socket ready).
2. Run the five commands above to preflight and capture.
3. Debug with `watch` + `press/move`; keep notes in `.context/.../agent_handoff.md` or `Docs/Issues/`.
4. Re-run `lib-verify-all` after ROM rebuilds.

## Headless / CI (when GUI is impossible)
- `./scripts/agent_workflow_start.sh --rom Roms/oos168x.sfc` (spins up yaze server + exports).
- `./scripts/agent_workflow_stop.sh` to tear down.
- Prefer socket control (`mesen2_client.py`) with deterministic `MESEN2_SOCKET_PATH` when headless.

## Paths that matter
- ROMs: `Roms/`
- Saves: `Roms/SaveStates/`
- Labels: keep `<rom>.mlb` next to the ROM (export via yaze or `export_symbols.py`).
- Stability references: `Docs/STABILITY.md` (color math clears, SPC timeouts, input hygiene).

## Sanity checks (rare but handy)
```
ls -ld /Applications/Mesen2\ OOS.app
./scripts/mesen2_sanity_check.sh --instance <name>   # checks socket + ROM alignment
```

## Optional helpers
- `python3 scripts/mesen2_client.py` or `scripts/mesen2_client_lib/bridge.py` for scripted socket access.
- `~/src/tools/hyrule-historian` for disasm/RAM lookups.
- `~/src/tools/expert-chain` only when you need multi-model analysis; otherwise avoid noise.
