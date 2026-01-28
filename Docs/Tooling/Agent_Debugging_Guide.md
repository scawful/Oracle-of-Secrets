# Agent Debugging Guide - Oracle of Secrets

This guide details the consolidated debugging infrastructure for Oracle of Secrets, optimized for AI agents and automated workflows.

## 1. Core Tools

The primary entry point for debugging is `scripts/mesen2_client.py`. It communicates with Mesen2 via a Unix Domain Socket for high-speed, reliable control.

### Consolidated Status & Discovery
- `python3 scripts/mesen2_client.py debug-status`: High-level summary of emulator health, game mode, location, and available canon states.
- `python3 scripts/mesen2_client.py debug-context`: Comprehensive discovery of all debugging assets (watch profiles, warps, items, flags).
Note: `mesen2_client.py` requires an explicit `--socket` or `--instance` (or set `MESEN2_AUTO_ATTACH=1` to auto-select the newest socket).

## 2. Symbolic Debugging (USDASM Integration)

We integrate the vanilla "Link to the Past" (USDASM) disassembly to provide context for both vanilla and custom routines.

- `python3 scripts/mesen2_client.py labels-sync`: Uploads 7600+ vanilla labels to Mesen2 so the GUI and CLI show symbolic names.
- `python3 scripts/mesen2_client.py symbols <query>`: Resolve a name to an address or vice-versa.
- `python3 scripts/mesen2_client.py disasm <address|label>`: Disassemble code with symbolic resolution.

Notes:
- `labels-sync` filters non-ROM addresses; if you still see RAM labels at `$00:00xx`, clear labels and resync.
- For Oracle labels, prefer the `oos168x.mlb` produced by `scripts/export_symbols.py --sync` (uses `MESEN2_HOME` when set).

## 3. Save State Management

We maintain a library of "Canon States" which are verified, stable points in the game.

- `python3 scripts/mesen2_client.py library`: List all states in the manifest.
- `python3 scripts/mesen2_client.py lib-verify-all`: Automatically verify all canon states by loading them and checking for crashes or stalls.
- `python3 scripts/mesen2_client.py lib-save "<label>"`: Capture the current state as a "draft" in the library.
- `python3 scripts/mesen2_client.py lib-verify <state_id>`: Promote a draft state to canon status.

## 4. Bug Reproduction Workflow

1. **Find a canon state** near the issue using `debug-status` or `library`.
2. **Reproduce**:
   ```bash
   python3 scripts/mesen2_client.py repro <state_id> --trace --watch overworld
   ```
   This command loads the state, sets the watch profile, and starts an execution trace (legacy DebugBridge). For socket-side trace control, use `TRACE` start/stop/status/clear (see `Docs/Tooling/Mesen2_Architecture.md`).
3. **Analyze**: Use `disasm` and `symbols` to investigate the code around the crash or bug.

## 4.1 Isolated Mesen2 Instance (agent-safe)

When another agent (or a human) is already using Mesen2, launch an isolated instance with its own profile, title, and state library set. This avoids clobbering any live sessions or shared SaveStates.

```bash
# Safe default: isolated profile + title + state library applied
./scripts/mesen2_launch_instance.sh

# Explicit instance name/title (recommended when multiple agents run)
./scripts/mesen2_launch_instance.sh \
  --instance codex-scawful \
  --owner codex-scawful \
  --title codex-scawful \
  --source codex \
  --state-set oos168x_current
```

Notes:
- The launcher defaults to an isolated `MESEN2_HOME` (macOS: `~/Library/Application Support/Mesen2-instances/<instance>`).
- Save-state library sets are applied into that profile’s `SaveStates/` and `Saves/` folders.
- Use `--no-state-set` to skip copying if you want a clean slate.
- Only use `--allow-default-profile` if you explicitly intend to share the default Mesen2 profile.
- The launcher seeds `settings.json` from your default profile to avoid input reset prompts; use `--copy-settings-force` if the instance config gets corrupted.
- Use `--copy-from <profile_dir>` if you want to seed from a specific profile (e.g., play vs dev).
- Default instance name is `<source>-<owner>` (reusable); pass `--instance <name>` for a one-off profile.

## 5. Agent Brain Integration

For autonomous movement and intelligent state tracking, use the `AgentBrain` class:

```python
from agent.brain import AgentBrain
agent = AgentBrain()
agent.goto(target_tx, target_ty)  # Screen-relative tile movement
agent.validate_and_save(slot=1)   # Safe save with collision checking
```

## 6. Resource Locations

| Resource | Path |
|----------|------|
| State Library | `Docs/Testing/save_state_library.json` |
| USDASM Labels | `z3dk/.context/knowledge/label_index_usdasm.csv` |
| Watch Profiles | `scripts/mesen2_client_lib/constants.py` |
| Game Constants | `scripts/mesen2_client_lib/constants.py` |
