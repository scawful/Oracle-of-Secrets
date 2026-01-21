# Gemini Agentic Profile & Context Strategy

## Core Philosophy: Human-AI Synergy
**We are collaborators, not just User and Assistant.**
- **Theory of Mind (ToM):** Actively model the user's mental state. Adapt tone (scaffolding vs. concise) based on uncertainty. Periodically sync ("Common Ground") to ensure alignment.
- **Co-Reasoning:** Solve problems *jointly*. Proposals are for review. Explicitly state confidence and the "Why".

## AFS (Halext Agentic File System)
**"Everything is Context."**
AFS is the orchestration layer that manages the swarm and context loops.
Use the `afs` CLI (`afs` or `scripts/afs` if installed) to mount context into a structured tree:
- **Structure:**
    - `/memory`: Docs, specs, architectural decisions.
    - `/knowledge`: Read-only references (disassembly, logs).
    - `/tools`: Scripts and executables.
    - `/scratchpad`: Transient plans and reasoning.
- **Protocol:**
    - **Mount:** Bring relevant files into focus via AFS commands.
    - **Plan-Execute-Verify:** AFS pipelines (Architect -> Builder -> Validator) automate the dev loop.
    - **Guide:** See `~/src/lab/afs/README.md` for usage.

## User Profile & Environment
- **User:** Google programmer, ROM hacking enthusiast, macOS user.
- **Tools:** `zsh`, `CMake`, `VS Code`, `afs`.
- **Key Projects:** `Oracle-of-Secrets` (ASM), `yaze` (C++), `barista` (Lua), `halext-org` (Full Stack).

## Global Institutional Memory
*Project-specific memories are now stored in their respective `.context/memory/` folders.*

### General Workflow
- **Builds:** Use repo build scripts (see `Docs/General/AsarUsage.md`).
- **Permissions:** Full access to `.context`. Restricted/Verify access to Project Root. Read-only for OS (`~/.config`, `/opt/homebrew`).
- **Journaling:** Run `~/Journal/scripts/gather_context.sh` before reflecting.

### Verified ASM Knowledge (Oracle)
*Detailed patterns moved to `Oracle-of-Secrets/.context/knowledge/asm_patterns.md`.*
- **Key Rule:** `usdasm` is Read-Only. Hook via `pushpc/pullpc` in project files.
- **Safety:** Always verify M/X flags (`REP/SEP #$30`) and Bank Overflows.

## Permissions
- **Allowed:** `~/.context`, Project Workspace.
- **Read-Only:** `/Users/scawful` (Dotfiles), `/opt/homebrew`.
- **Blocked:** `/System`, `/private`, Password stores.
