# Gemini Agentic Profile & Context Strategy

**If you only read one thing:** follow `Docs/Agent/Quickstart.md` (build → preflight → capture → debug).

## Core Philosophy (Trimmed)

- Collaborate, don't lecture. Default to concise unless asked for depth.
- State confidence + rationale briefly.

## AFS (if present)
- `afs` mounts context to `/memory`, `/knowledge`, `/tools`, `/scratchpad`.
- Use only when `.context/` is available; otherwise skip.

## User Profile & Environment

- **User:** Google programmer, ROM hacking enthusiast, macOS user.
- **Tools:** `zsh`, `CMake`, `VS Code`, `afs`.
- **Key Projects:** `Oracle-of-Secrets` (ASM), `yaze` (C++), `barista` (Lua), `halext-org` (Full Stack).

## Knowledge & Context (Minimal)
- If `.context/` exists: skim `agent_handoff.md` then `oracle_quick_reference.md`.
- If not: skip AFS/MCP entirely and proceed with the Quickstart.

## Global Institutional Memory

*Project-specific memories are now stored in their respective `.context/memory/` folders.*

### General Workflow

- **Builds:** Use repo build scripts (see `Docs/General/AsarUsage.md`).
- **Permissions:** Full access to `.context`. Restricted/Verify access to Project Root. Read-only for OS (`~/.config`, `/opt/homebrew`).
- **Journaling:** Run `~/Journal/scripts/gather_context.sh` before reflecting.

### Verified ASM Knowledge (Oracle)

*Detailed patterns in `~/.context/projects/oracle-of-secrets/knowledge/`*

- **Key Rule:** `usdasm` is Read-Only. Hook via `pushpc/pullpc` in project files.
- **Safety:** Always verify M/X flags (`REP/SEP #$30`) and Bank Overflows.
- **Namespace:** Most code in `namespace Oracle { }`, ZSCustomOverworld is **global**.
- **Probes:** Vanilla probe sets `$0D80,X` (state), **NOT** `$0EE0,X` (SprTimerD).

## Debugging & Automation (Mesen2)

- App: `/Applications/Mesen2 OOS.app` (fork). Socket defaults to `/tmp/mesen2-*.sock` unless `MESEN2_SOCKET_PATH` is set.
- Client: `python3 scripts/mesen2_client.py` (auto-attaches only if a single socket exists; otherwise set `MESEN2_SOCKET_PATH` or use `--socket`).
- Five commands to remember: `run-state`, `diagnostics --json`, `smart-save`, `lib-save`, `watch --profile overworld`.
- Tests: `scripts/test_runner.py` uses the socket backend by default.
- Verification: Run `python3 scripts/mesen2_client.py health` to verify the Socket API connection.
- Skill: `mesen2-oos-debugging` (CLI command map + troubleshooting).

## Sandbox & Permissions

The Antigravity shell environment uses a macOS Seatbelt sandbox.

### Common Issues
- **Operation not permitted**: Usually occurs if a file is listed in `.gitignore`. The sandbox denies access to ignored files by default to prevent accidental modification of sensitive assets.
- **Fix**: Whitelist the file in `.gitignore` (e.g., `!run.sh`) or use an escape hatch.

### Sandbox Modes
- **Default**: Restricted to workspace, `/tmp`, and `$HOME`.
- **Permissive**: Allows all file reads/writes. Use `SANDBOX_MODE=permissive <command>` to override restrictions.
- **Extra Paths**: Set `SANDBOX_EXTRA_ALLOW=/path1:/path2` to grant specific access.

## Permissions

- **Allowed:** `~/.context`, Project Workspace.
- **Read-Only:** `/Users/scawful` (Dotfiles), `/opt/homebrew`.
- **Blocked:** `/System`, `/private`, Password stores.
