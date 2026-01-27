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

- App: `/Applications/Mesen2 OOS.app` (fork). Socket auto-starts at `/tmp/mesen2-*.sock`.
- Client: `python3 scripts/mesen2_client.py` (use `MESEN2_SOCKET_PATH` if multiple).
- Five commands to remember: `run-state`, `diagnostics --json`, `smart-save`, `lib-save`, `watch --profile overworld`.
- Tests: `scripts/test_runner.py` uses the socket backend by default (`OOS_TEST_BACKEND=cli` forces legacy).
- Fallback Lua bridge: `scripts/mesen_cli.sh` only after starting `mesen_socket_server.py` + `mesen_launch.sh --bridge socket`.
- Headless option: `./scripts/agent_workflow_start.sh --rom Roms/oos168x.sfc`; stop with `agent_workflow_stop.sh`.

## Permissions

- **Allowed:** `~/.context`, Project Workspace.
- **Read-Only:** `/Users/scawful` (Dotfiles), `/opt/homebrew`.
- **Blocked:** `/System`, `/private`, Password stores.
