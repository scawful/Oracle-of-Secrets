# Root Cause Debugging Workflow

Repeatable six-phase workflow for debugging Oracle of Secrets bugs (black screen, softlock, transition hang, corruption) from reproduction to documented root cause. Use this pipeline with the tools listed below.

---

## 1. Tool Inventory

### Skills (invoke when relevant)

| Skill | Use when |
|-------|----------|
| **oracle-debugger** | Full debugging session: regression, ROM diff, trace, state library, bug repro, ASM validation, hypothesis testing. Entry: `python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py` |
| **mesen2-oos-debugging** | Socket CLI: breakpoint/trace, memory inspection, savestate repro, symbol resolution. Discovery: `MESEN2_SOCKET_PATH` → `/tmp/mesen2-*.status` (socketPath) → `/tmp/mesen2-*.sock` by mtime. |
| **zelda-debugger** | Black screen, transition hangs, INIDISP/GameMode/Submodule; P_WATCH, mem_watch, test harness, hypothesis_test. |
| **alttp-disasm-labels** | Mapping ROM/CPU addresses to labels; Hyrule Historian MCP first, then `rg` in usdasm. |
| **hyrule-navigator** | Getting Link to a location for repro: `goto --poi`, `enter --entrance`, etc. |

### MCPs (when Oracle/Zelda context loads)

| MCP | Purpose |
|-----|---------|
| **yaze-debugger** | YAZE ROM debugging via gRPC (if enabled). |
| **mesen2** | SNES emulator integration (if separate from mesen2-oos CLI). |
| **book-of-mudora** | Oracle-of-Secrets codebase reference, ROM map checks, hook validation. |
| **hyrule-historian** | Zelda disassembly and RAM search; symbol/address lookup (`lookup("Link_Main")`, `lookup("$07A123")`). |

### Runtime / Scripts

| Location | Tool | Purpose |
|----------|------|---------|
| [scripts/](../../scripts/) | `mesen2_client.py` | Health, diagnostics, state, breakpoints, trace, blame, symbols. **Preflight:** `diagnostics --json`, `run-state`. |
| Same | `repro_stack_corruption.py` | Automated repro with watch/blame for SP/corruption bugs. |
| Same | `oracle_debugger/orchestrator.py` | Unified orchestrator: `--monitor`, `--investigate <state.mss>`. |
| Same | `export_symbols.py --sync` | Sync Oracle labels into Mesen2 (use after z3ed; not vanilla-only). |
| Same | `run_regression_tests.sh` | Run tests from [tests/manifest.json](../../tests/manifest.json) (smoke, regression, full). |
| mesen2-oos | Socket API | 70+ commands: BREAKPOINT (with condition), CPU, TRACE, MEM_WATCH_WRITES, MEM_BLAME, P_WATCH, P_LOG, STACK_RETADDR, SYMBOLS_LOAD, SYMBOLS_RESOLVE. Discovery: `~/src/hobby/mesen2-oos/docs/Agent_Integration_Guide.md`. |

### Static analysis and symbols

| Tool | Location | Purpose |
|------|----------|---------|
| **z3dk** | `~/src/hobby/z3dk/` | `oracle_analyzer.py --rom Roms/oos168x.sfc --check-hooks --find-mx` (M/X call-site mismatches); `oracle_validate.py` for ROM integrity. |
| **z3ed (yaze)** | `yaze/build_ai/bin/Debug/z3ed` | `rom-resolve-address --address=<PC> --rom=Roms/oos168x.sfc --format=json`; dungeon-list-sprites; code_graph.py for call graph. |
| **Sentinel / crash_dump** | `yaze/scripts/ai/` | Background watchdog and crash reports with annotated traces. |

### AFS orchestrator (optional)

- **nayru** agent: 65816 ASM expertise. Invoke for interpreting traces or reviewing hook/flag behavior: `python3 lab/afs/tools/orchestrator.py --agent nayru --prompt "..."`.

---

## 2. Six-Phase Workflow

### Phase 1: Reproduce

**Goal:** Reliably trigger the bug (same state + same actions).

**Actions:**

- Use a **state from the state library** (or create one at the failure point): `mesen2_client.py load <slot>`, `lib-load "label"`, or `smart-save` / `lib-save`.
- If the bug is scripted: run **repro script** (e.g. `repro_stack_corruption.py`) or **test harness** from zelda-debugger skill (`test_harness.py --test building_entry`).
- For navigation-dependent bugs: use **hyrule-navigator** to get to the POI/entrance, then capture state.

**Output:** Reproducible steps + savestate path/slot.

---

### Phase 2: Capture

**Goal:** Snapshot failure state so it can be replayed and inspected.

**Actions:**

- **Preflight:** `python3 scripts/mesen2_client.py diagnostics --json` (and `run-state`).
- On failure: **pause**, then capture: **CPU** (registers), **savestate** (slot or lib-save with label), **screenshot** if useful.
- Store captures under `~/.context/projects/oracle-of-secrets/debug_captures/` (or project States/) and note path in the issue doc.

**Output:** Savestate file, diagnostics JSON, and a short “what was happening” description.

---

### Phase 3: Instrument

**Goal:** Add observability so the **exact** instruction or write that causes the bug can be identified.

**Actions:**

- **Conditional breakpoints** (e.g. SP corruption): break when `sp >= 0x0200` or on TCS with `a >= 0x0200` (see [RootCause_Investigation_Handoff.md](../Issues/RootCause_Investigation_Handoff.md)).
- **P_WATCH** (zelda-debugger / mesen2_client): depth 500–2000 to catch SEP/REP/PLP that corrupt P before a suspicious instruction.
- **MEM_WATCH** on key addresses (e.g. GameMode `$7E0010`, Submodule `$7E0011`, INIDISP `$7E001A`, or stack page); then use **MEM_BLAME** after hit.
- Reload the **same savestate** from Phase 2 and replay; when breakpoint or watch fires, leave emulation paused for Phase 4.

**Output:** Breakpoint/watch configuration and the pause point (PC, SP, key RAM values).

---

### Phase 4: Isolate

**Goal:** Get the precise PC(s) and, if applicable, the instruction that wrote to a given address.

**Actions:**

- **TRACE** (e.g. 500 instructions) from current PC backward to see the sequence leading to the fault.
- **MEM_BLAME** for the address of interest (e.g. INIDISP or stack) to get writer PC and opcode.
- **STACK_RETADDR** (RTL decode) to see call chain.
- Correlate with **P_LOG** if P_WATCH was used (confirm M/X at the faulting instruction).

**Output:** Faulting PC, opcode, and (if applicable) call chain and P state.

---

### Phase 5: Map to source

**Goal:** Turn PC into file:line and routine name for a fix.

**Actions:**

- **SYMBOLS_RESOLVE** (socket): `addr=<PC>` to get symbol/label.
- **z3ed:** `z3ed rom-resolve-address --address=<PC> --rom=Roms/oos168x.sfc --format=json`.
- **Hyrule Historian MCP** (alttp-disasm-labels): lookup by address or symbol; then `rg` in usdasm/jpdasm or in oracle-of-secrets ASM.
- **book-of-mudora** MCP: ROM map and hook context if the PC is in a hook.
- **z3dk:** `oracle_analyzer.py --check-hooks --find-mx` to see if that routine has M/X mismatches; use for context, not as sole root cause.

**Output:** Routine name, source file, and line (or bank+offset); optional call graph from code_graph.py.

---

### Phase 6: Document and validate

**Goal:** Record root cause and verify fix.

**Actions:**

- **Create or update** a doc in [Docs/Issues/](../Issues/) (e.g. `*_RootCause.md` or `*_Debug.md`). Follow the structure of [HUD_Artifact_Bug.md](../Issues/HUD_Artifact_Bug.md): Problem, Root Cause, Key commit/files, and optionally “Historical investigation” (ruled-out hypotheses).
- **Hypothesis testing:** Use zelda-debugger’s `hypothesis_test.py` or oracle-debugger’s hypothesis API to test a minimal patch (e.g. SEP/REP wrapper) before committing.
- **Regression:** Run `run_regression_tests.sh` (or manifest suites) and add/update a test in [tests/](../../tests/) if the bug is critical (e.g. stack_corruption, golden_path_overworld).

**Output:** Updated issue doc, passing regression, and optional new test JSON.

---

## 3. Root Cause Doc Template

When writing a root cause document, use this structure (see [HUD_Artifact_Bug.md](../Issues/HUD_Artifact_Bug.md)):

- **Problem Description** – What the user sees.
- **Resolution** – Status (FIXED / OPEN), commit if fixed, one-paragraph cause.
- **Technical Details** – Root cause, key commit, files affected.
- **Historical Investigation** (optional) – Ruled-out hypotheses.

---

## 4. Artifact Locations

| Artifact | Path |
|----------|------|
| Bug docs | [Docs/Issues/](../Issues/) |
| Savestates / state library | `Roms/SaveStates/`, `Roms/SaveStates/library/` |
| Debug captures | `~/.context/projects/oracle-of-secrets/debug_captures/` (create on first use if needed) |
| Regression tests | [tests/](../../tests/), [tests/manifest.json](../../tests/manifest.json) |
| Handoff for current P0 | [RootCause_Investigation_Handoff.md](../Issues/RootCause_Investigation_Handoff.md) |

---

## 5. Applying to Current P0 (Overworld Softlock)

The [Root Cause Investigation Handoff](../Issues/RootCause_Investigation_Handoff.md) narrows the overworld softlock to **SP corruption → DBR=0x50 → main dispatch in RAM**. The missing piece is **which instruction writes SP into the 0x0Dxx page**.

- **Phase 1–2:** Use save state slot 1 (overworld softlock), press A; capture savestate and diagnostics when black screen occurs (already documented).
- **Phase 3:** Add **conditional breakpoint** `sp >= 0x0200` (or break on TCS with `a >= 0x0200`). Reload state 1, resume, trigger; when it hits, leave paused.
- **Phase 4:** Run **TRACE** and **STACK_RETADDR** at that pause; note the instruction that just ran (e.g. TCS) and the call chain.
- **Phase 5:** **SYMBOLS_RESOLVE** / **z3ed** / Hyrule Historian on that PC; grep in oracle-of-secrets ASM for the routine name.
- **Phase 6:** Fill “TBD” in [OverworldSoftlock_RootCause.md](../Issues/OverworldSoftlock_RootCause.md) with exact PC, source file, and instruction; run regression and document verification.

---

## See Also

- [Debugging Tools Index](Debugging_Tools_Index.md)
- [Root Cause Investigation Handoff](../Issues/RootCause_Investigation_Handoff.md)
- [Agent Workflow](AgentWorkflow.md)
- [Mesen2 Architecture](Mesen2_Architecture.md)
