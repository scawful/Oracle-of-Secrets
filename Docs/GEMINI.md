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

## Knowledge System (CRITICAL)

**Oracle of Secrets uses a multi-layer knowledge system. Agents MUST query these proactively.**

### Layer 1: Memory Graph (MCP)

The memory graph contains structured knowledge about the project. **Query at session start:**

```
mcp__memory__search_nodes("Oracle")
```

**Key entities:**
| Entity | Contents |
|--------|----------|
| `OracleOfSecrets` | Project overview, lessons learned |
| `OracleMemoryMap` | Bank $20-$41 allocations |
| `OracleSRAMLayout` | Save RAM addresses ($7EF000+) |
| `OracleWRAMLayout` | Working RAM ($7E0000+) |
| `OracleSpriteFramework` | Sprite patterns, addresses |
| `OracleVanillaRoutines` | Key vanilla calls with addresses |
| `OracleKnownIssues` | Active bugs and gotchas |
| `Oracle65816Patterns` | Code conventions |
| `VanillaProbeSystem` | Probe detection (uses $0D80,X!) |
| `ZSCustomOverworld` | Area types, transition rules |

**Before modifying vanilla systems:**
```
mcp__memory__open_nodes(["VanillaProbeSystem", "OracleVanillaRoutines"])
```

### Layer 2: AFS Knowledge Docs

**Location:** `~/.context/projects/oracle-of-secrets/knowledge/`

| Document | Read When |
|----------|-----------|
| `oracle_quick_reference.md` | Starting ANY Oracle task |
| `sprite_development_guide.md` | Sprite work |
| `debugging_patterns.md` | Bug investigation |
| `architecture_diagram.mmd` | Understanding structure |

### Layer 3: Scratchpad (Session State)

**Location:** `~/.context/projects/oracle-of-secrets/scratchpad/`

| File | Purpose |
|------|---------|
| `agent_handoff.md` | **READ FIRST** - Current status, cross-session coordination |
| `debugging_session_*.md` | Complex investigation logs |

### Proactive Knowledge Protocol

**At Session Start:**
1. `mcp__memory__search_nodes("Oracle")` - Check for relevant entities
2. Read `agent_handoff.md` - Get current project status
3. Check `OracleKnownIssues` - Avoid known pitfalls

**During Work:**
1. Before modifying code → Query memory for related systems
2. After discovering something → Add observations to entities
3. If hitting a bug → Check `debugging_patterns.md` first

**At Session End:**
1. Update memory graph with new discoveries:
   ```
   mcp__memory__add_observations({
     observations: [{
       entityName: "OracleKnownIssues",
       contents: ["New issue: description"]
     }]
   })
   ```
2. Update `agent_handoff.md` with session summary
3. Create `Docs/Issues/<name>.md` for significant bugs

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

We use a **Dual-Backend Architecture** to support both interactive debugging (GUI) and high-speed CI (Headless) with a unified API.

### Active Mesen2 Repo

- Use `~/src/third_party/forks/Mesen2` for all emulator changes.
- Avoid upstream or alternate clones unless explicitly requested.
- If multiple clones look active, compare recent activity (e.g., `git log -1 --stat` or timestamps) and ask.

### 1. The Unified CLI (`scripts/mesen_cli.sh`)

This script acts as the primary interface for agents. It automatically detects if the Socket Hub is running.

```bash
# Common Commands
./scripts/mesen_cli.sh state            # Get JSON game state
./scripts/mesen_cli.sh press A          # Press button
./scripts/mesen_cli.sh read 0x7E0010    # Read memory
./scripts/mesen_cli.sh loadstate /path/to/state.mss
./scripts/mesen_cli.sh status           # Human-readable status
./scripts/mesen_cli.sh screenshot       # Capture frame
```

### 2. Backend Modes

- **Interactive (GUI):**
    1. Start Hub: `python3 scripts/mesen_socket_server.py`
    2. Open Mesen2 → Debug → Script Window → Load `scripts/mesen_socket_bridge.lua`
        - Or launch with `./scripts/mesen_launch.sh --bridge socket`
    3. *Best for:* Visual confirmation, "shoulder-surfing", reproducing bugs.

- **Headless (CI):**
    1. Start Server: `cd ~/src/tools/mesen2-mcp && python3 -m mesen2_mcp.server`
    2. *Best for:* Fast regression testing, automated agents.

### Yaze Background Service

Use `scripts/yaze_service.sh` to run a headless yaze server and toggle a GUI instance when needed:

```bash
./scripts/yaze_service.sh sync-nightly
./scripts/yaze_service.sh start --rom Roms/oos168x.sfc
./scripts/yaze_service.sh gui-toggle --rom Roms/oos168x.sfc
```

## Permissions

- **Allowed:** `~/.context`, Project Workspace.
- **Read-Only:** `/Users/scawful` (Dotfiles), `/opt/homebrew`.
- **Blocked:** `/System`, `/private`, Password stores.
