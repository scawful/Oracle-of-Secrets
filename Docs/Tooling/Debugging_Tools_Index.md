# Oracle of Secrets Debugging Tools Index

Comprehensive reference for all debugging tools available for Oracle of Secrets development.

## Quick Reference

| Tool | Location | Purpose | When to Use |
|------|----------|---------|-------------|
| **Sentinel** | `~/src/hobby/yaze/scripts/ai/sentinel.py` | Real-time soft lock detection | Continuous monitoring during play |
| **Crash Investigator** | `~/src/hobby/yaze/scripts/ai/crash_dump.py` | Post-mortem analysis | After crash/breakpoint hit |
| **Profiler** | `~/src/hobby/yaze/scripts/ai/profiler.py` | CPU hotspot analysis | Finding performance bottlenecks |
| **Fuzzer** | `~/src/hobby/yaze/scripts/ai/fuzzer.py` | Automated stress testing | Finding edge-case crashes |
| **State Query** | `~/src/hobby/yaze/scripts/ai/state_query.py` | Semantic game state queries | Scripting tests |
| **Code Graph** | `~/src/hobby/yaze/scripts/ai/code_graph.py` | Static ASM analysis | Finding callers/writers |
| **Memory Cartographer** | `~/src/hobby/yaze/scripts/ai/memory_cartographer.py` | RAM searching | Finding unknown addresses |
| **Oracle Debugger** | `~/.claude/skills/oracle-debugger/` | Unified platform | Comprehensive sessions |
| **mesen2_client.py** | `~/src/hobby/oracle-of-secrets/scripts/mesen2_client.py` | CLI interface | Direct emulator control |
| **Campaign CLI** | `~/src/hobby/oracle-of-secrets/scripts/campaign/` | Autonomous campaign tooling | Repeatable milestone checks + dashboards |
| **Campaign Autonomous Debugger** | `~/src/hobby/oracle-of-secrets/scripts/campaign/autonomous_debugger.py` | Softlock/anomaly monitor + auto-capture | Overnight runs + CI smoke validation |

---

## Mesen2 Socket Quickstart (USDASM-safe)

Use this flow to spin up the fork with a live socket, load a known state, and run B010/B-Mirror checks. All disassembly references must be **USDASM (US)** at `../usdasm`.

### Agent-safe isolated instance (preferred)

This creates a **separate Mesen2 home + title** and applies a save-state library set into that profile, avoiding interference with other agents or live play sessions.

```bash
# 1) Launch isolated Mesen2 instance (safe defaults)
./scripts/mesen2_launch_instance.sh

# 2) Use the socket explicitly (printed by the launcher)
python3 scripts/mesen2_client.py --socket /tmp/mesen2-<source>-<owner>.sock health
```

Notes:
- The launcher applies the `oos168x_current` state set by default (from `Docs/Testing/save_state_library.json`).
- Use `--no-state-set` for a clean profile or `--state-set <name>` to pick a different set.
- The launcher prints `MESEN2_HOME`, `MESEN2_SOCKET_PATH`, and `MESEN2_INSTANCE` exports for reuse.
- Default instance name is `<source>-<owner>` (reusable); pass `--instance <name>` for a one-off profile.
- Only use `--allow-default-profile` if you explicitly intend to share Mesen2’s default profile.
- The launcher seeds `settings.json` from your default profile to avoid input reset prompts; use `--copy-settings-force` if the instance config gets corrupted.
- `mesen2_client.py` requires explicit `--socket` or `--instance` (or set `MESEN2_AUTO_ATTACH=1` to auto-select the newest socket).

### Legacy/compat (manual launch)

```bash
# Manual launch with explicit env (keeps other instances safe)
export MESEN2_HOME="$HOME/Library/Application Support/Mesen2-instances/manual"
export MESEN2_SOCKET_PATH="/tmp/mesen2-manual.sock"
export MESEN2_AGENT_TITLE="manual"
export MESEN2_AGENT_SOURCE="manual"

"/Applications/Mesen2 OOS.app/Contents/MacOS/Mesen2" Roms/oos168x.sfc --instanceName=manual

# Verify socket is live
python3 scripts/mesen2_client.py --socket "$MESEN2_SOCKET_PATH" health

# Apply a state set to this profile (optional)
python3 scripts/state_library.py set-apply --set oos168x_current \
  --mesen-dir "$MESEN2_HOME/SaveStates" --mesen-saves-dir "$MESEN2_HOME/Saves"
```

Tips:
- Use USDASM only (never `jpdasm`) when mapping PCs: `../usdasm/bank_00.asm`.
- For a new set of states, refresh via `scripts/state_library.py capture` so CRCs match the current ROM.
- Socket trace control is now supported via `TRACE` (start/stop/status/clear + count/offset). See `Docs/Tooling/Mesen2_Architecture.md`.

---

## Tool Categories

### 1. Real-Time Monitoring

#### Sentinel (`~/src/hobby/yaze/scripts/ai/sentinel.py`)

Autonomous soft lock watchdog that runs continuously during gameplay.

**Detects:**
- **B007**: Y-coordinate overflow (Y > 60000)
- **B009**: Unexpected game reset (Mode 0x00 after gameplay)
- **INIDISP**: Black screen (0x80 sustained during gameplay)
- **Mode 0x06**: UnderworldLoad stuck > 2 seconds
- **Transitions**: Mode/Submode unchanged > 5 seconds
- **Stagnation**: Link position unchanged > 10 seconds

**Usage:**
```bash
cd ~/src/hobby/yaze
python3 scripts/ai/sentinel.py \
    --z3ed build_ai/bin/Debug/z3ed \
    --rom ~/src/hobby/oracle-of-secrets/Roms/oos168x.sfc
```

**Best Practice:** Run Sentinel in background during all testing sessions.

---

### 2. Autonomous Campaign

#### Campaign Autonomous Debugger (`oracle-of-secrets/scripts/campaign/autonomous_debugger.py`)

Monitors live gameplay and/or runs a campaign loop, detects softlocks/anomalies, and captures artifacts.

**Usage:**
```bash
# Monitor manual play (artifacts default to /tmp/oos_autodebug)
python3 -m scripts.campaign.autonomous_debugger --monitor

# Run the campaign orchestrator with monitoring injected
python3 -m scripts.campaign.autonomous_debugger --campaign

# CI-friendly: fail non-zero if any anomaly is detected
python3 -m scripts.campaign.autonomous_debugger --monitor --fail-on-anomaly --trace-count 2000
```

**Artifact locations (defaults):**
- Reports: `/tmp/oos_autodebug/reports`
- Savestates: `/tmp/oos_autodebug/states`

### 3. Post-Mortem Analysis

#### Crash Investigator (`~/src/hobby/yaze/scripts/ai/crash_dump.py`)

Captures execution traces and generates detailed crash reports with symbol resolution.

**Features:**
- Captures last 1000 frames of execution trace
- Resolves addresses to ASM symbols via `z3ed`
- Generates markdown reports with code snippets
- Monitor mode polls for breakpoint hits

**Usage:**
```bash
# Monitor for crashes/pauses
python3 scripts/ai/crash_dump.py monitor

# Immediate dump
python3 scripts/ai/crash_dump.py dump
```

**Output:** `~/src/hobby/yaze/crash_reports/crash_*.md`

---

### 4. Performance Analysis

#### Profiler (`~/src/hobby/yaze/scripts/ai/profiler.py`)

Statistical CPU sampling to identify performance hotspots.

**Features:**
- PC sampling (500 instructions per snapshot)
- Symbol resolution to identify routines
- Aggregation by function name

**Usage:**
```bash
python3 scripts/ai/profiler.py --duration 10  # Profile for 10 seconds
```

**When to Use:** Game feels slow? Profile to find which routines consume CPU time.

---

### 5. Stress Testing

#### Fuzzer / Chaos Monkey (`~/src/hobby/yaze/scripts/ai/fuzzer.py`)

Automated random input generation to discover edge-case crashes.

**Modes:**
- `gameplay` - Natural movement + button presses (discovery)
- `glitch` - High-frequency frame-perfect inputs (stress)

**Usage:**
```bash
# Standard gameplay fuzzing
python3 scripts/ai/fuzzer.py --mode gameplay --duration 60

# Glitch hunting
python3 scripts/ai/fuzzer.py --mode glitch --duration 30
```

**Best Practice:** Run overnight with Sentinel for autonomous crash discovery.

---

### 6. State Queries

#### State Query (`~/src/hobby/yaze/scripts/ai/state_query.py`)

High-level semantic queries about game state for scripting.

**Queries:**
- `is_safe`, `is_overworld`, `is_dungeon`, `can_control`
- `has <item>`, `rupees`

**Usage:**
```bash
python3 scripts/ai/state_query.py is_safe
python3 scripts/ai/state_query.py has bow
```

---

### 7. Static Analysis

#### Code Graph (`~/src/hobby/yaze/scripts/ai/code_graph.py`)

Build call graphs and find memory write locations.

**Commands:**
- `graph` - Export full call graph to JSON
- `callers <label>` - Find all callers of a routine
- `writes <address>` - Find all routines that write to an address

**Usage:**
```bash
ORACLE_DIR=~/src/hobby/oracle-of-secrets

# Find who calls a routine
python3 scripts/ai/code_graph.py $ORACLE_DIR callers CheckForFollowerInterroomTransition

# Find who writes to Link Y
python3 scripts/ai/code_graph.py $ORACLE_DIR writes 7E0020
```

**When to Use:** Investigating which code path modifies a value.

---

### 8. Memory Searching

#### Memory Cartographer (`~/src/hobby/yaze/scripts/ai/memory_cartographer.py`)

Cheat Engine-style memory searching for unknown addresses.

**Filters:**
- `changed` - Value changed since baseline
- `stable` - Value stayed same
- `increased` - Value went up
- `value <n>` - Exact value match

**Usage:**
```bash
python3 scripts/ai/memory_cartographer.py interactive
# > start 0x7E0000 0x7E0100
# > update
# > filter changed
# > report
```

**When to Use:** Finding undocumented RAM addresses.

---

### 9. Oracle Debugger Skill (`~/.claude/skills/oracle-debugger/`)

Claude skill wrapper providing additional capabilities:

**Usage:**
```bash
# Interactive session
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py interactive

# Regression tests (uses test suite)
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py regression

# Bug reproduction
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py reproduce "black screen on building entry"

# ROM comparison
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py diff old.sfc new.sfc
```

---

### 10. CLI Interface

#### mesen2_client.py (`~/src/hobby/oracle-of-secrets/scripts/mesen2_client.py`)

Direct emulator control via command line.

**Key Commands:**
```bash
# State inspection
python3 scripts/mesen2_client.py state --json
python3 scripts/mesen2_client.py diagnostics --deep --json

# Save state management
python3 scripts/mesen2_client.py smart-save 1
python3 scripts/mesen2_client.py lib-save "Crash repro state"

# Debugging (NEW)
python3 scripts/mesen2_client.py breakpoint --profile transition
python3 scripts/mesen2_client.py breakpoint --add 0x0289BF:exec

# Navigation
python3 scripts/mesen2_client.py navigate --poi "lost_woods_center"

# Control
python3 scripts/mesen2_client.py pause
python3 scripts/mesen2_client.py press "a,up" --frames 10

# Session Logging (NEW)
# Logs all commands and arguments to a JSONL file
python3 scripts/mesen2_client.py --log session.jsonl navigate --poi "beach"
```

---

## Root Cause Debugging (Six-Phase Workflow)

For taking any bug from reproduction to documented root cause, use the **Root Cause Debugging Workflow**:

- **[Root_Cause_Debugging_Workflow.md](Root_Cause_Debugging_Workflow.md)** – Tool inventory (skills, MCPs, scripts, z3dk/z3ed) and six phases: **Reproduce → Capture → Instrument → Isolate → Map to source → Document and validate**. Each phase lists actions, tools, and outputs. Use this for black screen, softlock, transition hang, or corruption bugs.

Phases in brief:
1. **Reproduce** – State library, repro script, or test harness; get reproducible steps + savestate.
2. **Capture** – Preflight diagnostics; on failure: pause, CPU/savestate/screenshot; store under `~/.context/projects/oracle-of-secrets/debug_captures/`.
3. **Instrument** – Conditional breakpoints (e.g. `sp >= 0x0200`), P_WATCH, MEM_WATCH; reload savestate and replay until breakpoint/watch fires.
4. **Isolate** – TRACE, MEM_BLAME, STACK_RETADDR, P_LOG to get faulting PC and opcode.
5. **Map to source** – SYMBOLS_RESOLVE, z3ed, Hyrule Historian, book-of-mudora, z3dk; get routine name and source file.
6. **Document and validate** – Update `Docs/Issues/*_RootCause.md` (see [HUD_Artifact_Bug.md](../Issues/HUD_Artifact_Bug.md) template); hypothesis test; run regression.

---

## Debugging Workflows

### Workflow 1: Investigating a Known Soft Lock

```bash
# 1. Start Sentinel monitoring
python3 ~/src/hobby/yaze/scripts/ai/sentinel.py &

# 2. Load repro state and trigger the bug
python3 scripts/mesen2_client.py load 7

# 3. Sentinel auto-captures when soft lock detected
# Check crash report:
cat ~/src/hobby/yaze/crash_reports/crash_*.md | tail -100

# 4. Static analysis - find who writes to the problem address
python3 ~/src/hobby/yaze/scripts/ai/code_graph.py ~/src/hobby/oracle-of-secrets writes 7E0020
```

### Workflow 2: Finding Unknown Crashes

```bash
# 1. Run Sentinel + Fuzzer in parallel
python3 ~/src/hobby/yaze/scripts/ai/sentinel.py &
python3 ~/src/hobby/yaze/scripts/ai/fuzzer.py --mode gameplay --duration 300

# 2. Review captured crash reports
ls ~/src/hobby/yaze/crash_reports/

# 3. Load the saved state to investigate
python3 scripts/mesen2_client.py lib-load "reproduced_*"
```

### Workflow 3: Performance Investigation

```bash
# 1. Start profiling during slow section
python3 ~/src/hobby/yaze/scripts/ai/profiler.py --duration 10

# 2. Review hotspots
# Output shows which routines consume most CPU

# 3. Investigate hot routine
python3 ~/src/hobby/yaze/scripts/ai/code_graph.py ~/src/hobby/oracle-of-secrets callers HotRoutineName
```

### Workflow 4: Full Regression Testing

```bash
# 1. Build new ROM
cd ~/src/hobby/oracle-of-secrets
./scripts/build_rom.sh 168

# 2. Run regression suite
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py regression

# 3. If failures, compare with previous ROM
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py diff Roms/oos167x.sfc Roms/oos168x.sfc
```

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Oracle Debugging Stack                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Real-Time Tools (YAZE)                       │    │
│  │  sentinel.py | fuzzer.py | profiler.py | memory_cartographer.py │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │                    Analysis Tools (YAZE)                          │  │
│  │  crash_dump.py | code_graph.py | state_query.py                   │  │
│  └─────────────────────────────────┼─────────────────────────────────┘  │
│                                    │                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │               Oracle Client Library (Oracle)                      │  │
│  │  mesen2_client_lib/ | mesen2_client.py                            │  │
│  └─────────────────────────────────┼─────────────────────────────────┘  │
│                                    │                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │              Unified Platform (Claude Skill)                      │  │
│  │  oracle-debugger/scripts/debugger.py                              │  │
│  └─────────────────────────────────┼─────────────────────────────────┘  │
│                                    │                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │                     Mesen2-OOS Socket API                         │  │
│  │  55+ commands | /tmp/mesen2-<pid>.sock                            │  │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## File Locations

| Category | Path |
|----------|------|
| **YAZE AI Tools** | `~/src/hobby/yaze/scripts/ai/` |
| **Oracle Client** | `~/src/hobby/oracle-of-secrets/scripts/mesen2_client_lib/` |
| **Oracle CLI** | `~/src/hobby/oracle-of-secrets/scripts/mesen2_client.py` |
| **Oracle Debugger Skill** | `~/.claude/skills/oracle-debugger/` |
| **Mesen2-OOS** | `~/src/hobby/mesen2-oos/` |
| **Crash Reports** | `~/src/hobby/yaze/crash_reports/` |
| **State Library** | `~/src/hobby/oracle-of-secrets/Roms/SaveStates/library/` |
| **Debug Captures** | `~/.context/projects/oracle-of-secrets/debug_captures/` |

---

## Dependencies

All tools require:
1. **Mesen2-OOS** running with socket server
2. **mesen2_client_lib** available in Python path
3. **z3ed** binary (for symbol resolution)

```bash
# Verify setup
python3 -c "from mesen2_client_lib.client import OracleDebugClient; print('Client OK')"
ls /tmp/mesen2-*.sock && echo "Socket OK"
~/src/hobby/yaze/build_ai/bin/Debug/z3ed --help && echo "z3ed OK"
```

---

## See Also

- [Root Cause Debugging Workflow](Root_Cause_Debugging_Workflow.md) – Six-phase workflow for root-cause debugging (Reproduce → Capture → Instrument → Isolate → Map → Document).
- [Mesen2 Architecture](Mesen2_Architecture.md)
- [Debugging Infrastructure Roadmap](Debugging_Infrastructure_Roadmap.md)
- [Agent Workflow](AgentWorkflow.md)
- [Blockers](../Campaign/Blockers.md)
