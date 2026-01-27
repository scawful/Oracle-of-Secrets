# Agent Workflow (Lean)

Use this file only when the one-page `Docs/Agent/Quickstart.md` is not enough. The goal is to keep every agent on the same minimal path.

## Core stack (preferred)
- Emulator: `/Applications/Mesen2 OOS.app` (fork with socket auto-start).
- Client: `python3 scripts/mesen2_client.py` (socket path auto-detected; set `MESEN2_SOCKET_PATH` if multiple).
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
- Only drop to `mesen_cli.sh` if you need Lua-bridge behavior; start `mesen_socket_server.py` + `mesen_launch.sh --bridge socket` first.

## Paths that matter
- ROMs: `Roms/`
- Saves: `Roms/SaveStates/`
- Labels: keep `<rom>.mlb` next to the ROM (export via yaze or `export_symbols.py`).
- Stability references: `Docs/STABILITY.md` (color math clears, SPC timeouts, input hygiene).

## Sanity checks (rare but handy)
```
ls -ld /Applications/Mesen2\ OOS.app
./scripts/mesen2_preflight.sh --rebuild-dirty   # rebuilds ROM+Mesen2 if stale/dirty
```

## Optional helpers
- `~/src/tools/mesen2-mcp` for scripted socket access.
- `~/src/tools/hyrule-historian` for disasm/RAM lookups.
- `~/src/tools/expert-chain` only when you need multi-model analysis; otherwise avoid noise.
