# Oracle of Secrets Debugging Tools Index

Comprehensive reference for all debugging tools available for Oracle of Secrets development.

## Quick Reference

| Tool | Location | Purpose | When to Use |
|------|----------|---------|-------------|
| **Sentinel** | `yaze/scripts/ai/sentinel.py` | Real-time soft lock detection | Continuous monitoring during play |
| **Crash Investigator** | `yaze/scripts/ai/crash_dump.py` | Post-mortem analysis | After crash/breakpoint hit |
| **Profiler** | `yaze/scripts/ai/profiler.py` | CPU hotspot analysis | Finding performance bottlenecks |
| **Fuzzer** | `yaze/scripts/ai/fuzzer.py` | Automated stress testing | Finding edge-case crashes |
| **State Query** | `yaze/scripts/ai/state_query.py` | Semantic game state queries | Scripting tests |
| **Code Graph** | `yaze/scripts/ai/code_graph.py` | Static ASM analysis | Finding callers/writers |
| **Memory Cartographer** | `yaze/scripts/ai/memory_cartographer.py` | RAM searching | Finding unknown addresses |
| **Oracle Debugger** | `~/.claude/skills/oracle-debugger/` | Unified platform | Comprehensive sessions |
| **mesen2_client.py** | `oracle-of-secrets/scripts/` | CLI interface | Direct emulator control |

---

## Mesen2 Socket Quickstart (USDASM-safe)

Use this flow to spin up the fork with a live socket, load a known state, and run B010/B-Mirror checks. All disassembly references must be **USDASM (US)** at `../third_party/usdasm`.

```bash
# 1) Launch Mesen2 with socket bridge (pick your instance name)
MESEN_APP="/Users/scawful/src/hobby/mesen2-oos/bin/osx-arm64/Release/osx-arm64/publish/Mesen2 OOS.app" \
MESEN2_AGENT_SOURCE=manual \
./scripts/mesen_launch.sh --bridge socket --rom Roms/oos168x.sfc \
  --state 1 --instance codex --multi --open-launch --export-env

# 2) Copy the matching savestate into the instance save dir
mkdir -p ~/.config/mesen2-codex/SaveStates
cp Roms/SaveStates/oos168x/oos168x_1.mss ~/.config/mesen2-codex/SaveStates/oos168x_1.mss

# 3) Verify socket is live (path printed by mesen_launch; fallback: ls /tmp/mesen2-*.sock)
MESEN2_SOCKET_PATH=/tmp/mesen2-1165.sock ./scripts/mesen_cli.sh status

# 4) Run the regression harness
MESEN2_SOCKET_PATH=/tmp/mesen2-1165.sock python3 scripts/savestate_regression.py --slot 1 --frames 600
```

Tips:
- If the window does not appear in a headless environment, the socket still works; interact via `mesen_cli.sh`.
- Use USDASM only (never `jpdasm`) when mapping PCs: `../third_party/usdasm/bank_00.asm`.
- For a new set of states, refresh via `scripts/state_library.py capture` so CRCs match the current ROM.

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

### 2. Post-Mortem Analysis

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

### 3. Performance Analysis

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

### 4. Stress Testing

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

### 5. State Queries

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

### 6. Static Analysis

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

### 7. Memory Searching

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

### 8. Unified Platform

#### Oracle Debugger (`~/.claude/skills/oracle-debugger/`)

Comprehensive debugging platform integrating multiple capabilities.

**Components:**
- Emulator control
- State library management
- Regression testing
- ROM diffing
- Trace analysis
- Bug reproduction
- ASM validation
- Hypothesis testing

**Usage:**
```bash
# Interactive session
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py interactive

# Regression tests
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py regression

# Bug reproduction
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py reproduce "black screen on building entry"

# ROM comparison
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py diff old.sfc new.sfc
```

---

### 9. CLI Interface

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

# Navigation
python3 scripts/mesen2_client.py warp --area 0x40 --x 256 --y 256
python3 scripts/mesen2_client.py navigate --poi "lost_woods_center"

# Control
python3 scripts/mesen2_client.py pause
python3 scripts/mesen2_client.py press "a,up" --frames 10
```

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

- [Mesen2 Architecture](Mesen2_Architecture.md)
- [Debugging Infrastructure Roadmap](Debugging_Infrastructure_Roadmap.md)
- [Agent Workflow](AgentWorkflow.md)
- [Blockers](../Campaign/Blockers.md)
