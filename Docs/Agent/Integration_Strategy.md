# Tool Integration Strategy

**Date:** 2026-01-21
**Status:** Implemented

## Current State

### What We Have

| Tool | Purpose | Integration Point |
|------|---------|-------------------|
| **mesen_live_bridge.lua** | Game state, input injection | File-based IPC |
| **yaze_bridge.lua** | Symbol sync to Mesen2 | HTTP API (yaze server) |
| **MoE Orchestrator** | Route prompts to Triforce models | CLI / Python API |
| **Triforce Models** | Specialized 65816 experts | LM Studio / Ollama |
| **z3ed** | AI-driven ROM hacking CLI | gRPC to yaze |

### What Was Missing (Now Implemented)

1. ~~**No test result routing**~~ → `test_runner.py` routes failures to experts
2. ~~**No visual capture**~~ → `visual_diff.py` + screenshot command
3. ~~**No unified test format**~~ → JSON test definitions in `tests/`
4. ~~**Bridges don't communicate**~~ → `yaze_sync.py` daemon

### Implemented Tools

| Script | Purpose | Usage |
|--------|---------|-------|
| `export_symbols.py` | WLA→MLB symbol conversion | `./scripts/export_symbols.py --sync` |
| `visual_diff.py` | Screenshot comparison | `./scripts/visual_diff.py compare a.png b.png` |
| `yaze_sync.py` | Bidirectional yaze↔Mesen2 sync | `./scripts/yaze_sync.py --status` |
| `ai_patch.py` | AI-suggested ASM patches | `./scripts/ai_patch.py interactive` |
| `test_runner.py` | Automated test execution | `./scripts/test_runner.py tests/*.json` |

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Test Orchestrator                            │
│  (Python script that coordinates all tools)                        │
└───────────────┬─────────────────────────────────┬──────────────────┘
                │                                 │
        ┌───────▼───────┐                 ┌───────▼───────┐
        │  mesen_cli.sh │                 │ MoE Orchest.  │
        │  (game state) │                 │ (AI routing)  │
        └───────┬───────┘                 └───────┬───────┘
                │                                 │
        ┌───────▼───────┐                 ┌───────▼───────┐
        │ Mesen2 Bridge │                 │ Triforce      │
        │ (Lua script)  │                 │ Nayru/Din/etc │
        └───────────────┘                 └───────────────┘
```

---

## Quick Wins (Can Do Now)

### 1. Add Screenshot Command to Bridge

**Why:** Enable visual regression testing without external tools.

**Implementation:**
```lua
-- In mesen_live_bridge.lua
elseif cmd == "SCREENSHOT" then
    local path = responseMode == "pipe" and parts[3] or parts[2]
    path = path or (BRIDGE_DIR .. "/screenshot.png")
    emu.takeScreenshot(path)
    response = "SCREENSHOT:" .. path
```

```bash
# In mesen_cli.sh
cmd_screenshot() {
    local path="${1:-}"
    ensure_bridge || return 1
    send_command "SCREENSHOT" "${path:-}"
}
```

**Impact:** Can capture game state visually, diff against baselines.

---

### 2. Orchestrator-Driven Test Runner

**Why:** Route test failures to the right expert automatically.

**Implementation:** `scripts/test_runner.py`

```python
#!/usr/bin/env python3
"""Orchestrator-driven test runner for Oracle of Secrets."""

import subprocess
import json
import sys
from pathlib import Path

# Expert routing based on failure type
FAILURE_ROUTES = {
    "crash": "farore",       # Debugging expert
    "collision": "veran",    # Hardware/register expert
    "visual": "nayru",       # Code analysis
    "performance": "din",    # Optimization expert
}

def run_mesen_command(cmd: str, *args) -> str:
    """Execute mesen_cli.sh command."""
    result = subprocess.run(
        ["./scripts/mesen_cli.sh", cmd, *args],
        capture_output=True, text=True
    )
    return result.stdout

def route_to_expert(failure_type: str, context: str) -> str:
    """Route failure to appropriate Triforce model."""
    expert = FAILURE_ROUTES.get(failure_type, "farore")
    result = subprocess.run(
        ["python3", "~/src/lab/afs/tools/moe_orchestrator.py",
         "--force", expert,
         "--prompt", f"Analyze this test failure:\n{context}"],
        capture_output=True, text=True
    )
    return result.stdout

def run_test(test_def: dict) -> dict:
    """Execute a single test and return results."""
    # Load save state (manual step - user loads in Mesen2)
    print(f"Load save state: {test_def['state']}")
    input("Press Enter when ready...")

    # Execute test sequence
    for step in test_def["steps"]:
        if step["type"] == "press":
            run_mesen_command("press", step["button"], str(step.get("frames", 5)))
        elif step["type"] == "wait":
            import time
            time.sleep(step["seconds"])
        elif step["type"] == "assert":
            value = run_mesen_command("read", step["address"])
            # Parse and verify...

    return {"passed": True, "details": "..."}
```

**Impact:** Automated test execution with AI-powered failure analysis.

---

### 3. Unified Test Definition Format

**Why:** One format for save states, test steps, and expected results.

**Format:** `tests/lr_swap_test.json`

```json
{
  "name": "L/R Hookshot Swap",
  "description": "Verify L/R buttons toggle between hookshot and goldstar",
  "saveState": "items/hookshot_both.mss",
  "preconditions": {
    "$7EF342": {"equals": 2, "desc": "Has both items"},
    "$7E0202": {"equals": 3, "desc": "Hookshot slot equipped"}
  },
  "steps": [
    {"type": "assert", "address": "$7E0739", "equals": 0, "desc": "Starts as hookshot"},
    {"type": "press", "button": "L", "frames": 5},
    {"type": "wait", "seconds": 0.1},
    {"type": "assert", "address": "$7E0739", "equals": 2, "desc": "Switched to goldstar"},
    {"type": "press", "button": "R", "frames": 5},
    {"type": "wait", "seconds": 0.1},
    {"type": "assert", "address": "$7E0739", "equals": 1, "desc": "Switched to hookshot"}
  ],
  "onFailure": {
    "route": "farore",
    "context": "L/R swap toggle not working. Check HandleLRSwap routine."
  }
}
```

**Impact:** Declarative tests that are human-readable and machine-executable.

---

### 4. Symbol Export for Labeling

**Why:** Oracle-of-Secrets has its own symbols. Share them with Mesen2.

**Implementation:** Add to build process:

```bash
# Extract symbols from .sym file and convert to .mlb format
./scripts/export_symbols.sh > ~/Documents/Mesen2/Debug/oos168x.mlb
```

**Mesen2 auto-loads .mlb files matching ROM name.**

**Impact:** Better debugging with meaningful labels in Mesen2.

---

## Medium-Term Integrations

### 5. Visual Regression Pipeline

```
1. Run test → capture screenshot (bridge)
2. Compare to baseline (ImageMagick/perceptual hash)
3. If diff > threshold → route to AI for analysis
4. AI describes what changed (sprite corruption, missing tiles, etc.)
```

### 6. yaze ↔ Mesen2 Bidirectional Sync

Currently: yaze → Mesen2 (symbols only)
Goal: Mesen2 → yaze (breakpoint triggers, PC sync)

This enables:
- Break in Mesen2 → yaze jumps to that code
- Edit in yaze → Mesen2 reloads symbols

### 7. z3ed Integration for Patching

```bash
# AI-suggested fix from test failure
z3ed --rom oos168x.sfc --prompt "Fix water collision in room 0x27"
# → Nayru generates ASM
# → yaze applies patch
# → Re-run test
```

---

## Implementation Status

| Priority | Item | Status | Script |
|----------|------|--------|--------|
| **P0** | Screenshot command | ✅ Done | `mesen_cli.sh screenshot` |
| **P0** | Unified test format | ✅ Done | `tests/*.json` |
| **P1** | Test runner script | ✅ Done | `test_runner.py` |
| **P1** | Symbol export | ✅ Done | `export_symbols.py` |
| **P2** | Visual regression | ✅ Done | `visual_diff.py` |
| **P2** | Bidirectional sync | ✅ Done | `yaze_sync.py` |
| **P3** | z3ed patching loop | ✅ Done | `ai_patch.py` |

---

## Next Steps

1. **Implement P0 items** (screenshot, test format)
2. **Create sample test** using unified format
3. **Run end-to-end** with L/R swap test
4. **Iterate** based on real-world usage

---

## Questions to Resolve

1. Should test definitions live in `Roms/SaveStates/` (gitignored) or `tests/` (tracked)?
2. Do we need real-time streaming from Mesen2 or is polling sufficient?
3. How do we handle save state loading (still manual F1-F10)?
