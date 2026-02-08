# Ralph Codex Loop (Autonomous OOS Debugging Suite)

Purpose: run an autonomous “ralph wiggum” loop that plays and debugs Oracle of Secrets using Codex GPT‑5.2‑xhigh, with strict awareness of emulator‑level controls vs in‑game state. Lives outside `oracle-of-secrets/scripts` to avoid further pollution; everything is referenced via config and AFS.

Key design points
- AFS-first: discovers `.context` roots for oracle-of-secrets, mesen2-oos, z3dk, yaze/z3ed; logs to `~/.context/projects/oracle-of-secrets/scratchpad/sessions/`.
- Tool awareness: uses Mesen2 fork socket (`mesen2_client.py`), yaze/z3ed for headless, z3dk/usdasm knowledge mounts, AFS Triforce model registry + embeddings (paths configurable).
- Emulator vs game control: separates run/pause/frame-step from in-game inputs; enforces run-state checks before navigation; detects black/blank screens and bad collision.
- Input gate: blocks inputs when paused/cutscene/transition/black screen; use `--resume` to explicitly resume before running inputs.
- Instance-aware: prefers a named Mesen2 instance (via `MESEN2_INSTANCE` / `mesen_instance`) to avoid crossing streams with your manual session.
- Navigation-ready: path runner stubs call into navigator helpers (Collision/Overworld) and log every step (area/module/submode/scroll/X/Y).
- Extensible: main agent is Codex GPT‑5.2‑xhigh, with consult hooks for Gemini 3.0 Flash Preview, Claude Opus 4.5, and local LMStudio Zelda-tuned models (Din/Nayru/Farore).

Quickstart (manual)
```bash
cd oracle-of-secrets/Tools/ralph-codex-loop
python3 ralph_loop.py diag          # discover contexts, sockets, run-state
python3 ralph_loop.py attach        # attach to live Mesen2 socket; prints state
python3 ralph_loop.py nav-demo      # stub path runner (spawn→house/pyramid)
python3 ralph_loop.py nav-run spawn_to_pyramid  # execute predefined path with safe inputs
python3 ralph_loop.py nav-run spawn_to_pyramid --resume  # explicitly resume if paused
python3 ralph_loop.py nav-run dw_softlock_south --allow-danger  # run a path marked as dangerous
python3 ralph_loop.py detect        # run black-screen + spawn-flag detectors
python3 ralph_loop.py explore --steps 10  # autonomous exploration with deep validation
python3 ralph_loop.py explore --steps 10 --resume  # resume if paused during preflight/steps
python3 ralph_loop.py explore --steps 10 --fallback-input --max-softlocks 2  # force RAM input + abort on softlocks
python3 ralph_loop.py consult "question" --model claude_opus  # subagent consult stub
python3 ralph_loop.py log-session "note"  # append to session log
```

Configuration
- Defaults live in `config.yaml` (paths to ROMs, sockets, contexts, model catalog).
- Override via env vars: `MESEN2_INSTANCE`, `MESEN2_SOCKET_PATH`, `RALPH_ROM`, `RALPH_LOG`.
- `mesen_instance` (default: `agent`) tells the loop which registry instance to attach to; avoids grabbing the wrong socket.
- Safety knobs: `input_chunk_frames` (split long directional holds) and `dangerous_paths` (block known risky paths unless `--allow-danger`).
- Model catalog:
  - `gpt-5.2-codex-xhigh` (primary)
  - `gemini-3.0-flash-preview-01-28`
  - `claude-opus-4.5`
  - `din` / `nayru` / `farore` via LMStudio HTTP (localhost:1234 default)

Outputs
- Session logs: `~/.context/projects/oracle-of-secrets/scratchpad/sessions/<date>_ralph.md`
- Latest socket hint: `.context/scratchpad/mesen2/latest_socket.txt` (if present)
- Diagnostic captures: `Docs/Planning/Status/ralph/diag_*.json` (created on demand)

Next steps (recommended)
- Wire real path planner to Collision/Overworld navigator (use nav_attach.sh).
- Add richer detectors (INIDISP already logged; add BG tilemap checksum) and auto smart-save on failure.
- Integrate state library migration (`state_sync.py`) + >99 slot handling.
- Add headless yaze/z3ed runner for parity checks and ASM consult hooks when needed.

Utilities
- `mesen2_autostart.sh`: launch a named Mesen2 instance (agent-safe) with ROM/Lua override.
- `scripts/mesen2_launch_instance.sh`: standalone launcher that sets `MESEN2_HOME`, instance GUID, and registry claim.
- `state_sync.py`: ingest legacy OOS91x `.mss` files (Roms/SaveStates/oos91x) into library/legacy and emit manifest.
- Secrets: `~/.secrets` is auto-read for API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.) before consult calls.
