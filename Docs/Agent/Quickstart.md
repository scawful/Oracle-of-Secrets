# Agent Quickstart (One Page)

Use this before any other Oracle-of-Secrets doc. It is the shortest path to reproduce, debug, and hand off fixes.

## Defaults
- Repo: `~/src/hobby/oracle-of-secrets`
- ROMs: `Roms/oos168x.sfc` (release), `Roms/oos168_test2.sfc` (dev/edit)
- Emulator: `/Applications/Mesen2 OOS.app` (socket auto-starts at `/tmp/mesen2-*.sock`)
- Client CLI: `python3 scripts/mesen2_client.py`

## Five-Step Loop
1) **Build (skip if fresh):** `./scripts/build_rom.sh 168`
2) **Launch Mesen2 + open ROM.** Prefer `./scripts/mesen2_launch_instance.sh` for isolated sessions. If you launch manually and multiple sockets exist, set `MESEN2_SOCKET_PATH=/tmp/mesen2-<pid>.sock`.
3) **Preflight:** When multiple Mesen2 instances exist, set `MESEN2_SOCKET_PATH` or use `--socket` so the client targets the right instance.
   - `python3 scripts/mesen2_client.py run-state`
   - `python3 scripts/mesen2_client.py diagnostics --json`
   - `python3 scripts/mesen2_client.py lib-verify-all` (guards against stale savestates)
4) **Repro + capture:**
   - `python3 scripts/mesen2_client.py smart-save 5 --label "<bug>"`
   - `python3 scripts/mesen2_client.py lib-save "<bug>"`
   - Optional snapshot for notes: `python3 scripts/mesen2_client.py capture --json`
5) **Debug/fix:** use `watch --profile overworld`, `state-diff`, `press/move`, and `labels-sync` as needed. Log the result in `.context/.../scratchpad/agent_handoff.md` (if present) or `Docs/Issues/`.

## Stability Guardrails (read once)
- **Color math:** Overworld transitions must clear CGADDSUB + COLDATA mirrors (`$9A/$9C/$9D`). See `Docs/STABILITY.md#1-ppu-register-management` before touching overlays.
- **APU timeouts:** All SPC handshakes go through `SPC_Upload_WithTimeout` in `Core/patches.asm`. Do not add unbounded polls.
- **Input injection:** Prefer socket inputs (`press`, `navigate`, `setInputOverrides`) over direct WRAM writes to avoid desyncs.
- **Savestate hygiene:** Run `lib-verify-all` after rebuilding; re-export states if mismatched.

## If Tooling Misbehaves
- Socket missing? Relaunch Mesen2 and run `python3 scripts/mesen2_client.py socket-cleanup`.
- Input prefs reset prompt? Relaunch with `./scripts/mesen2_launch_instance.sh --copy-settings-force`.
- Mesen2 older than repo? Rebuild the fork (`cd ../mesen2-oos && make`) and relaunch, or run `./scripts/mesen2_sanity_check.sh --instance <name>`.
- Need headless/CI? `./scripts/agent_workflow_start.sh --rom Roms/oos168x.sfc` (details in `Docs/Tooling/AgentWorkflow.md`).
- Need deeper background? Check `Docs/STABILITY.md` and `Docs/General/Troubleshooting.md` only after the quickstart.
