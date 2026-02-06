## Quick Start

1. **Read AFS context** — `MEMORY.md` loads automatically; then read `scratchpad/agent_handoff.md` for current priorities
2. **Find anything** — Use `CONTEXT_INDEX.md` to route any concept to its authoritative file
3. **Check context** — Read relevant `knowledge/` docs before modifying code
4. **Debug preflight** — `python3 scripts/mesen2_client.py run-state` + `diagnostics --json`
5. **Capture repro state** — `python3 scripts/mesen2_client.py smart-save 1`
6. **Document progress** — Update `scratchpad/agent_handoff.md` during/after work

### Mesen2 Socket & Symbols

- **Discovery:** `MESEN2_SOCKET_PATH` → `/tmp/mesen2-*.status` (read `socketPath`) → `/tmp/mesen2-*.sock` by mtime. Do not assume PID in socket name. See `~/src/hobby/mesen2-oos/docs/Agent_Integration_Guide.md`.
- **Symbols:** `SYMBOLS_LOAD` accepts `file` or `path`; formats JSON or Mesen `.mlb`. `SYMBOLS_RESOLVE` with `addr=` resolves address→symbol. API: `~/src/hobby/mesen2-oos/docs/Socket_API_Reference.md`.
- **STEP:** `mode` can be `into`, `over`, or `out`.

---

## Agentic File System (AFS)

The AFS is the structured context layer that lives outside the project repo. It gives agents persistent memory, reference docs, and working state across sessions.

### Location

```
~/.context/projects/oracle-of-secrets/
```

### Structure

```
├── CONTEXT_INDEX.md        # Concept→file routing table (read after MEMORY.md)
├── metadata.json           # AFS policies and directory config
│
├── knowledge/              # REFERENCE (read-mostly)
│   ├── oracle_quick_reference.md    # RAM, banks, code patterns
│   ├── sprite_development_guide.md  # Sprite template + vanilla routines
│   ├── asm_patterns.md              # Addressing modes, hitboxes, input
│   ├── debugging_patterns.md        # Bug patterns, transitions, regression
│   ├── OoS_Code_Guidelines.md      # Register preservation, hooks, banks
│   ├── ZSOW_v3_Integration.md      # Overworld engine memory map
│   ├── debug_info.md               # Auto-generated warp/item/flag tables
│   └── architecture_diagram.mmd    # Mermaid architecture graph
│
├── memory/                 # LONG-TERM CONSTRAINTS (writable)
│   └── technical_debt.md   # 9 tracked debt items by severity
│
├── scratchpad/             # WORKING MEMORY (writable, ephemeral)
│   ├── agent_handoff.md           # Current priorities + session state
│   ├── next_session_prompt.md     # Focused task prompt for next agent
│   ├── active_investigations.md   # Live bug tracking with repro/root cause
│   ├── lessons_learned.md         # Pre-debug checklist, common patterns
│   └── state.md                   # Progress tracking
│
├── history/                # Event log (append-only)
├── global/                 # Reserved (cross-project, empty)
├── hivemind/               # Reserved (cross-session learning, empty)
├── items/                  # Reserved (empty)
└── tools/                  # Reserved (empty)
```

### How to Use the AFS

**Session start — read in this order:**

1. `MEMORY.md` — Auto-loaded. Contains Quick Nav, gotchas, SRAM layout, dialogue reference
2. `scratchpad/agent_handoff.md` — Current priorities, what was established last session
3. `scratchpad/next_session_prompt.md` — Specific task instructions (if set)
4. `CONTEXT_INDEX.md` — Look up any concept → find the right file

**Finding information:**

The `CONTEXT_INDEX.md` maps every Oracle concept to its authoritative file(s), organized by domain:
- Assembly & Code Patterns
- Sprite Development
- Overworld & Transitions
- Debugging & Testing
- Story & Dialogue
- World Building
- Items & Masks
- Tooling & Build
- Technical Debt & Issues

Example: need sprite hitbox info? → CONTEXT_INDEX → `knowledge/asm_patterns.md`
Example: need D4 dungeon map? → CONTEXT_INDEX → `Docs/World/Dungeons/Dungeons.md`

**During work:**

- Before modifying code: check CONTEXT_INDEX for related systems
- If you hit a bug: read `knowledge/debugging_patterns.md` first
- After discovering something new: add to `scratchpad/active_investigations.md` or `memory/technical_debt.md`

**When finishing:**

1. Update `scratchpad/agent_handoff.md` with session summary
2. Update `memory/technical_debt.md` if new debt discovered
3. Create issue doc if bug found: `Docs/Issues/<name>.md`

### Policies

| Directory | Access | Purpose |
|-----------|--------|---------|
| `knowledge/` | Read-only | Reference docs — don't modify without good reason |
| `memory/` | Writable | Long-term constraints (technical debt, specs) |
| `scratchpad/` | Writable | Working memory, session state, investigations |
| `history/` | Append-only | Event logs |

### AFS vs Repo Docs

- **AFS paths** (`knowledge/`, `memory/`, `scratchpad/`): relative to `~/.context/projects/oracle-of-secrets/`
- **Repo paths** (`Core/`, `Sprites/`, `Docs/`, `Items/`): relative to `~/src/hobby/oracle-of-secrets/`
- **`MEMORY.md`**: the auto-loaded agent memory file
- **`project CLAUDE.md`**: this file

The AFS holds agent-facing context (how to work on the project). The repo `Docs/` directory holds project documentation (what the project is). The CONTEXT_INDEX.md bridges both.

---

## Current Priorities

**Source of truth:** `scratchpad/agent_handoff.md`

### Priority 1: D6 Goron Mines Minecarts (Make Rooms Playable)

Goal: make the four flagged rooms playable by aligning minecart spawn placement, track IDs, and custom collision.

- **Rooms:** `0xA8`, `0xB8`, `0xD8`, `0xDA` (see `Docs/Plans/goron_mines_minecart_design.md`)
- **Validation (CLI):** `../yaze/scripts/z3ed dungeon-minecart-audit --rom Roms/oos168x.sfc --rooms 0xA8,0xB8,0xD8,0xDA --only-issues`
- **Fix checklist:**
  - Cart sprites (`0xA3`) are placed on stop tiles (`0xB7`-`0xBA`)
  - Cart `SprSubtype` matches the rail object (`0x0031`) subtype used in the room
  - Switch corners (`0xD0`-`0xD3`) and `Sprite_SwitchTrack` (`0xB0`) are placed when puzzle routing requires them
- **Guardrails:** `!ENABLE_MINECART_PLANNED_TRACK_TABLE`, `!ENABLE_MINECART_CART_SHUTTERS`

### Priority 2: Maku Tree Hint Cascade (Complete, Needs Dialogue)

The dispatch logic is wired for D1-D7 in `Sprites/NPCs/maku_tree.asm`, but the messages are placeholders.

- **Messages:** `Core/message.asm` (`Message_1C5`-`Message_1D1`)
- **TODO(dialogue):** replace placeholder bytes with real text; keep IDs stable.

### Priority 3: D4 Water Gate Hooks (Enabled, Needs Runtime Regression)

Hooks are enabled behind feature flags; the remaining work is runtime regression coverage.

- **Flags:** `!ENABLE_WATER_GATE_HOOKS`, `!ENABLE_WATER_GATE_OVERLAY_REDIRECT`
- **Next:** Mesen2 regression pass (D1-D7 enter/exit) plus D4 end-to-end water fill persistence.

### Priority 4: Progression Helpers (Complete, Start Conversions)

Shared helpers exist in `Core/progression.asm` (`GetCrystalCount`, `UpdateMapIcon`, `SelectReactionMessage`).

- **Next:** convert one NPC at a time (start with `Sprites/NPCs/zora.asm`) to use `SelectReactionMessage` to reduce scattered inline crystal checks.

### Tooling Direction (Guardrails)

- **Feature flags:**
  - Defaults live in `Util/macros.asm`
  - Overrides live in `Config/feature_flags.asm` (generated)
  - Gate risky hooks, and annotate org sites with `; @hook module=...` so `hooks.json` and `hack_manifest.json` stay accurate
- **z3dk:**
  - Prefer baseline-vs-current diffs (`oracle_analyzer_delta.py`) over chasing absolute warning counts
  - Keep analyzer reports in `/tmp` and commit only code/docs (no report dumps)

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

### 2. ZSCustomOverworld Transitions
**NEVER** modify coordinates (`$20-$23`) during transition flow.
Use post-transition hooks instead.

### 3. Collision Offsets
`TileDetect_MainHandler` adds +20 pixel Y offset before checking.
Visual water at Y=39 needs collision data at Y=41.

### 4. JumpTableLocal Y-Width
`JumpTableLocal ($008781)` requires 8-bit Y on entry (PLY pops 1 byte).
16-bit Y causes stack underflow. z3dk analyzer flags callers with Y=16-bit as errors.

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

**Test Suites:** See [`Docs/Testing/README.md`](Docs/Testing/README.md)

---

## Debugging Toolkit

**Full documentation:** [`Docs/Tooling/Debugging_Tools_Index.md`](Docs/Tooling/Debugging_Tools_Index.md)

### Unified Debugging Orchestrator (Recommended)

The `oracle_debugger` package coordinates all debugging tools in a single session.

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
-   **JumpTableLocal ($008781):** Requires 8-bit Y on entry (PLY pops 1 byte). 16-bit Y causes stack underflow (PLY pops 2 bytes). z3dk flags callers with Y=16-bit as errors.
-   **Build integration:** `build_rom.sh` invokes oracle_analyzer when available.
-   **Tests:** `pytest tests/test_mx_flag_analysis.py -v` (15 tests, no ROM required).

---

## Documentation Hierarchy

1. **This file** (`CLAUDE.md`) — Quick agent reference, AFS guide, priorities
2. **`CONTEXT_INDEX.md`** — Concept→file routing table (in AFS root)
3. **`MEMORY.md`** — Auto-loaded agent memory (gotchas, SRAM, dialogue)
4. **`Docs/General/DevelopmentGuidelines.md`** — Architecture rules
5. **`Docs/GEMINI.md`** — Full collaboration strategy
6. **`~/.context/projects/oracle-of-secrets/knowledge/`** — Technical references
7. **`~/.context/projects/oracle-of-secrets/scratchpad/`** — Session state
