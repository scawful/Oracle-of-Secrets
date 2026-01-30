---

## Ralph Loop Findings (2026-01-24)

### Critical Findings
- **Mesen2 Fork Instability:** Socket server crashes intermittently during script execution. Do not switch emulators; restart the fork and capture logs instead.
- **Black Screen Bug:** Tier 1 (Static Analysis) passed, but Tier 2 (Smoke Testing) and Tier 3 (State Capture) are **PENDING**. Do not assume it is fully fixed.
- **YAZE Save State Gap:** YAZE proto has save/load RPCs, but the MCP bridge exposure is **PENDING** (Task P1.3 in `Mesen2_Debug_Backlog.md`).

---

## Quick Start

1. **Read First:** Check `Docs/GEMINI.md` for the core profile and collaboration strategy
2. **Query Memory:** Search the knowledge graph before starting work
3. **Check Context:** Read relevant knowledge docs from `~/.context/projects/oracle-of-secrets/`
4. **Document Progress:** Update scratchpad and handoff docs during/after work
5. **Debug Preflight:** `python3 scripts/mesen2_client.py run-state` + `diagnostics --json`
   - Deep capture (items/flags/sprites/watch): `python3 scripts/mesen2_client.py diagnostics --deep --json`
6. **Capture Repro State:** `python3 scripts/mesen2_client.py smart-save 1` (slots 1-99 or configured)
   - Optional label: `python3 scripts/mesen2_client.py savestate-label set 1 --label "Dark World south crash"`
   - Library capture: `python3 scripts/mesen2_client.py lib-save "Dark World south crash"`

### Mesen2 socket and symbols
- **Discovery:** `MESEN2_SOCKET_PATH` → `/tmp/mesen2-*.status` (read `socketPath`) → `/tmp/mesen2-*.sock` by mtime. Do not assume PID in socket name. See `~/src/hobby/mesen2-oos/docs/Agent_Integration_Guide.md`.
- **Symbols:** `SYMBOLS_LOAD` accepts `file` or `path`; formats JSON or Mesen `.mlb`. `SYMBOLS_RESOLVE` with `addr=` resolves address→symbol. API: `~/src/hobby/mesen2-oos/docs/Socket_API_Reference.md`.
- **STEP:** `mode` can be `into`, `over`, or `out`.

---

## Knowledge System (IMPORTANT)

### Memory Graph - Query Before Coding

**Always query the memory graph at session start for Oracle work:**

```
mcp__memory__search_nodes("Oracle")
```

**Key entities to check:**
- `OracleOfSecrets` - Project overview, recent issues, lessons learned
- `OracleSRAMLayout` - Save RAM addresses and story flags
- `OracleWRAMLayout` - Working RAM addresses
- `OracleSpriteFramework` - Sprite development patterns
- `OracleVanillaRoutines` - Key vanilla addresses to call
- `OracleKnownIssues` - Active bugs and gotchas
- `Oracle65816Patterns` - Code conventions

**Before modifying vanilla behavior:**
```
mcp__memory__open_nodes(["VanillaProbeSystem", "ZSCustomOverworld"])
```

### AFS Knowledge Docs

**Located at:** `~/.context/projects/oracle-of-secrets/knowledge/`

| Document | When to Read |
|----------|--------------|
| `oracle_quick_reference.md` | Starting any Oracle task |
| `sprite_development_guide.md` | Creating/modifying sprites |
| `debugging_patterns.md` | Investigating bugs, post-regression |

**Read before implementation:**
```
Read ~/.context/projects/oracle-of-secrets/knowledge/oracle_quick_reference.md
```

### Scratchpad & Handoffs

**Located at:** `~/.context/projects/oracle-of-secrets/scratchpad/`

| File | Purpose |
|------|---------|
| `agent_handoff.md` | Cross-session coordination, current status |
| `debugging_session_*.md` | Session logs for complex investigations |

**Always check handoff at session start:**
```
Read ~/.context/projects/oracle-of-secrets/scratchpad/agent_handoff.md
```

---

## Proactive Knowledge Management

### When Starting a Session

1. Query memory graph for relevant entities
2. Read `agent_handoff.md` for current status
3. Check `OracleKnownIssues` for gotchas related to your task
4. Read relevant knowledge docs

### During Work

1. **Before modifying code:** Check memory graph for related systems
2. **After discovering something:** Add observations to relevant entities
3. **If you hit a bug:** Check `debugging_patterns.md` first

### When Finishing

1. **Update memory graph** with new discoveries:
   ```
   mcp__memory__add_observations({
     observations: [{
       entityName: "OracleKnownIssues",
       contents: ["New issue discovered: ..."]
     }]
   })
   ```

2. **Update handoff doc** with session summary
3. **Create issue doc** if bug found: `Docs/Issues/<name>.md`

---

## Code Patterns (Quick Reference)

### Namespace Rules
- Most code: `namespace Oracle { }`
- ZSCustomOverworld: **Outside namespace** (global)
- Cross-namespace: Prefix with `Oracle_`

### Routine Template
```asm
MyRoutine:
{
  PHB : PHK : PLB    ; Required bank setup
  ; ... code ...
  PLB
  RTL
}
```

### SRAM Flags
```asm
%SRAMSetFlag(OOSPROG, !Story_IntroComplete)
%SRAMCheckFlag(OOSPROG, !Story_IntroComplete) : BNE .has_flag
```

### Sprite State Machine
```asm
LDA.w SprAction, X
JSL JumpTableLocal
dw State_Idle, State_Chase, State_Attack
```

---

## Critical Gotchas

### 1. Vanilla Probe System
**WRONG:** `LDA.w SprTimerD, X` for probe detection
**RIGHT:** `LDA.w SprState, X` (vanilla sets `$0D80,X`, not `$0EE0,X`)

### 2. Black Screen Bug Status (2026-01-24)
- **Tier 1 (Static):** Long addressing and SEP/REP verified.
- **Tier 2 (Visual):** **PENDING**. Verification needed for all transitions (OW→Cave, etc.).
- **Infrastructure:** Use `oracle-debugger` skill or YAZE AI tools for autonomous capture.

### 3. ZSCustomOverworld Transitions
**NEVER** modify coordinates (`$20-$23`) during transition flow.
Use post-transition hooks instead.

### 3. Collision Offsets
`TileDetect_MainHandler` adds +20 pixel Y offset before checking.
Visual water at Y=39 needs collision data at Y=41.

---

## Build & Test

```bash
# Build (automatically runs smoke tests)
cd ~/src/hobby/oracle-of-secrets
./scripts/build_rom.sh 168

# Build without tests
SKIP_TESTS=1 ./scripts/build_rom.sh 168

# Run regression tests
./scripts/run_regression_tests.sh regression

# Run all tests
./scripts/run_regression_tests.sh full

# Test manually
~/src/tools/emu-launch -m Roms/oos168x.sfc

# Debug (Socket API)
python3 scripts/mesen2_client.py ping
python3 scripts/mesen2_client.py state --json
python3 scripts/mesen2_client.py run-state
python3 scripts/mesen2_client.py time
python3 scripts/mesen2_client.py diagnostics --json
```

**Test Suites:** See [`Docs/Testing/Regression_Test_Suite.md`](Docs/Testing/Regression_Test_Suite.md)

---

## Debugging Toolkit

**Full documentation:** [`Docs/Tooling/Debugging_Tools_Index.md`](Docs/Tooling/Debugging_Tools_Index.md)

### Unified Debugging Orchestrator (Recommended)

**NEW (2026-01):** The `oracle_debugger` package coordinates all debugging tools in a single session.

```bash
# Start continuous monitoring (recommended for bug hunting)
python3 scripts/oracle_debugger/orchestrator.py --monitor

# Investigate a specific save state
python3 scripts/oracle_debugger/orchestrator.py --investigate Roms/SaveStates/crash.mss

# With verbose MoE analysis
python3 scripts/oracle_debugger/orchestrator.py --monitor --verbose
```

**Features:**
- Coordinates Sentinel, crash dump, and static analysis
- Routes to MoE experts (Nayru, Veran, Farore, Din)
- Auto-generates regression tests from detections
- Produces Markdown reports in `crash_reports/`

**Documentation:** [`Docs/Tooling/Oracle_Debugger_Package.md`](Docs/Tooling/Oracle_Debugger_Package.md)

### Real-Time Tools (`~/src/hobby/yaze/scripts/ai/`)

| Tool | Purpose | Command |
|------|---------|---------|
| **Sentinel** | Soft lock detection | `python3 sentinel.py` |
| **Crash Dump** | Post-mortem analysis | `python3 crash_dump.py dump` |
| **Profiler** | CPU hotspots | `python3 profiler.py --duration 10` |
| **Fuzzer** | Stress testing | `python3 fuzzer.py --mode gameplay` |
| **Code Graph** | Static analysis | `python3 code_graph.py callers <label>` |

### Quick Debugging Workflow (Manual)

```bash
# 1. Start Sentinel monitoring (runs in background)
cd ~/src/hobby/yaze
python3 scripts/ai/sentinel.py &

# 2. Load repro state and play
python3 ~/src/hobby/oracle-of-secrets/scripts/mesen2_client.py load 1

# 3. Sentinel auto-captures when soft lock detected
# Check reports:
cat crash_reports/crash_*.md | tail -100

# 4. Static analysis if needed
python3 scripts/ai/code_graph.py ~/src/hobby/oracle-of-secrets writes 7E0020
```

### Skill-Based Platform

```bash
# Interactive debugging session
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py interactive

# Regression tests via skill
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py regression

# ROM comparison
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py diff old.sfc new.sfc
```

---

## Mesen2 Fork

-   **Active repo:** `~/src/hobby/mesen2-oos` (Socket Server enabled)
-   **Architecture:** [`Docs/Tooling/Mesen2_Architecture.md`](Docs/Tooling/Mesen2_Architecture.md)
-   **Golden Path:** Agents use **Socket API** (`/tmp/mesen2-*.sock`) via `mesen2_client.py` (see `mesen2-oos-debugging` skill).
-   **Socket discovery:** Set `MESEN2_SOCKET_PATH` env var. Fallback: glob by mtime. Do NOT use `MESEN2_SOCKET` (deprecated).
-   **Rule:** Only use `apps/Mesen2 OOS.app` (fork build). Do NOT use vanilla Mesen.

## Z3DK Integration

-   **Active repo:** `~/src/hobby/z3dk`
-   **Static analysis:** `scripts/oracle_analyzer.py --check-hooks --find-mx` validates M/X register state at hook entry points.
-   **JumpTableLocal ($008781):** Requires X=16-bit. z3dk flags callers with X=8-bit as errors.
-   **Build integration:** `build_rom.sh` invokes oracle_analyzer when available.
-   **Tests:** `pytest tests/test_mx_flag_analysis.py -v` (15 tests, no ROM required).

---

## Documentation Hierarchy

1. **This file** (`CLAUDE.md`) - Quick agent reference
2. **`Docs/GEMINI.md`** - Full collaboration strategy
3. **`Docs/General/DevelopmentGuidelines.md`** - Architecture rules
4. **`~/.context/projects/oracle-of-secrets/knowledge/`** - Technical references
5. **`~/.context/projects/oracle-of-secrets/scratchpad/`** - Session state
