# Tool Integration Strategy

**Date:** 2026-01-21
**Status:** Implemented

> NOTE (2026-02-07): This document describes a legacy Lua/file-bridge era (`mesen_live_bridge.lua`, `mesen_cli.sh`).
> Oracle of Secrets now uses the Mesen2 OOS fork socket API via `python3 scripts/mesen2_client.py` as the supported path.
> Keep this doc for historical context only.


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
    # Load save state via bridge (auto)
    state = test_def.get("saveState", {})
    if isinstance(state, dict) and state.get("path"):
        run_mesen_command("loadstate", state["path"])
        import time
        # Wait for savestate load to complete (fallback to short sleep if needed)
        run_mesen_command("wait-load", str(int(state.get("waitSeconds", 1.0))))

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
  "saveState": {
    "id": "hookshot_both",
    "path": "items/hookshot_both.mss",
    "libraryRoot": "Roms/SaveStates/library",
    "waitSeconds": 8,
    "reloadCaches": true
  },
  "preconditions": {
    "$7EF342": {"equals": 2, "desc": "Has both items"},
    "$7E0202": {"equals": 3, "desc": "Hookshot slot equipped"}
  },
  "steps": [
    {"type": "assert", "address": "$7E0739", "in": [0, 1], "desc": "Starts as hookshot"},
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
3. Save state loading can use `mesen_cli.sh loadstate` + a short sleep (or `wait-addr`); do we still need manual F1-F10 fallback?
