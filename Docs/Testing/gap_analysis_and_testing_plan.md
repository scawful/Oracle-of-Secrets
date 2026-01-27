# Oracle of Secrets - Testing Infrastructure Gap Analysis

> NOTE (2026-01-24): oos168x/oos168_test2 save states are deprecated. Use patched oos168x states only; stale packs are archived under `Roms/SaveStates/library/_stale_oos_20260124`.

**Date:** 2026-01-22
**Status:** Analysis Complete
**Priority:** Foundation work for automated regression testing

---

## Executive Summary

The Oracle of Secrets project has **sophisticated testing infrastructure** with comprehensive tooling, but critical **data gaps** prevent full automation. This document identifies gaps and proposes concrete testing setups.

### Key Findings

| Category | Status | Blocker? |
|----------|--------|----------|
| Test runner framework | ✅ Complete (706 lines) | No |
| Visual diff tooling | ✅ Complete (380 lines) | No |
| State library framework | ✅ Complete (400+ lines) | No |
| Save state files | ⚠️ Exist in Mesen2, not cataloged | **Yes** |
| Baseline screenshots | ❌ Empty | **Yes** |
| State library manifest | ❌ Empty | **Yes** |
| CI/CD emulator tests | ⚠️ Self-hosted only | Partial |
| Unit tests (pytest) | ❌ None | No |

---

## 1. Available Save States

### Mesen2 SaveStates Directory

Located at: `~/Documents/Mesen2/SaveStates/`

| ROM Build | Files | Date Range | Notes |
|-----------|-------|------------|-------|
| **oos168x** | 11 states (`oos168x_1.mss` - `oos168x_11.mss`) | Jan 21-22, 2026 | **Primary baseline** |
| oos168 | 11 states (`oos168_1.mss` - `oos168_11.mss`) | Jan 21, 2026 | Base ROM |
| **oos168x** | 11 states (`oos168x_1.mss` - `oos168x_11.mss`) | Jan 21-22, 2026 | Patched ROM (current) |
| spooky_test | 11 states | Oct-Nov 2023 | Halloween build |
| disco_dragon | 2 states | Jul 2023 | Side project |

### Recommended State Usage

**Primary baseline:** `oos168x` states

| State | Potential Use | Priority |
|-------|--------------|----------|
| `oos168x_1.mss` | Boot verification, basic overworld | High |
| `oos168x_2.mss` | Menu system testing | High |
| `oos168x_3.mss` | Item functionality | High |
| `oos168x_1.mss` | Current build regression | High |
| `oos168x_10.mss` | Latest state (Jan 22) | Medium |

---

## 2. Identified Gaps

### Gap 1: Empty State Library Manifest

**File:** `Docs/Testing/save_state_library.json`

```json
{
  "version": 1,
  "library_root": "Roms/SaveStates/library",
  "entries": [],  // EMPTY
  "sets": []      // EMPTY
}
```

**Impact:** Test runner cannot load states by ID. All automated tests fail at precondition phase.

**Fix:** Populate manifest with oos168x and oos168x states.

---

### Gap 2: No Baseline Screenshots

**Directory:** `tests/baselines/` (empty)

**Impact:** Visual regression testing (`visual_diff.py`) has no reference images. Cannot detect UI regressions.

**Fix:** Capture baselines for key scenarios:
- Title screen
- File select
- Overworld (various screens)
- Menu system
- Dungeon entrance
- Water gate rooms

---

### Gap 3: State Files Not Imported

**Issue:** States exist in `~/Documents/Mesen2/SaveStates/` but not copied to `Roms/SaveStates/library/`.

**Impact:** Test definitions reference paths that don't exist (e.g., `items/hookshot_both.mss`).

**Fix:** Import and categorize existing states.

---

### Gap 4: No Unit Tests for Python Scripts

**Current state:** All testing is integration-level (requires running emulator).

**Missing coverage:**
- `test_runner.py` command parsing
- `visual_diff.py` hash comparison
- `state_library.py` manifest operations
- `ai_patch.py` expert routing logic

**Fix:** Add pytest framework with mocked emulator calls.

---

### Gap 5: CI/CD Emulator Tests Conditional

**File:** `.github/workflows/test-rom.yml`

```yaml
emulator-tests:
  if: github.event_name == 'workflow_dispatch' || contains(github.event.head_commit.message, '[run-tests]')
  runs-on: self-hosted  # Requires local runner with Mesen2
```

**Impact:** Emulator tests don't run on regular pushes/PRs. Only ASM/Lua syntax checks run.

**Fix:** Document self-hosted runner setup, or create mock-based tests for CI.

---

### Gap 6: No Test Metrics Dashboard

**Current state:** Test results go to stdout and GitHub Actions summary. No historical tracking.

**Missing:**
- Pass/fail rate over time
- Regression detection
- Flaky test identification
- Coverage metrics

**Fix:** Implement `scripts/dashboard.html` data population.

---

## 3. Testing Setup Plans

### Phase 1: Foundation (Immediate)

#### Task 1.1: Import Save States to Library

```bash
# Copy oos168x states (primary baseline)
mkdir -p Roms/SaveStates/library/baseline
cp ~/Documents/Mesen2/SaveStates/oos168x_*.mss Roms/SaveStates/library/baseline/

# Copy current build states
mkdir -p Roms/SaveStates/library/oos168x
cp ~/Documents/Mesen2/SaveStates/oos168x_*.mss Roms/SaveStates/library/oos168x/
```

#### Task 1.2: Populate State Library Manifest

Create entries for each imported state with metadata (requires inspecting states with `mesen_state_inspector.lua`).

**Schema per entry:**
```json
{
  "id": "baseline_1",
  "path": "baseline/oos168x_1.mss",
  "romVersion": "oos168x",
  "description": "Opening sequence, fresh file",
  "tags": ["boot", "overworld", "early-game"],
  "gameState": {
    "mode": "0x09",
    "room": "0x22",
    "indoors": false
  }
}
```

#### Task 1.3: Capture Baseline Screenshots

Using `visual_diff.py capture`:

| Scenario | Baseline Name | Source State |
|----------|---------------|--------------|
| Title screen | `title_screen.png` | Boot from fresh |
| File select | `file_select.png` | Post-intro |
| Overworld starting area | `ow_start.png` | `baseline_1` |
| Menu opened | `menu_open.png` | Press START from ow |
| Water gate room (pre-fill) | `water_gate_pre.png` | Room 0x27 |
| Water gate room (post-fill) | `water_gate_post.png` | After activation |

---

### Phase 2: Automated Test Suite

#### Task 2.1: Create Core Test Cases

**Boot Verification Test** (`tests/boot_test.json`):
```json
{
  "name": "Boot Verification",
  "description": "Verify ROM boots to title screen without crash",
  "steps": [
    {"type": "wait", "seconds": 5},
    {"type": "assert", "address": "$7E0010", "equals": 0, "description": "Title screen mode"},
    {"type": "screenshot", "name": "boot_title"}
  ]
}
```

**Overworld Transition Test** (`tests/ow_transition_test.json`):
```json
{
  "name": "Overworld Transition",
  "description": "Walk between overworld screens without crash",
  "saveState": {"id": "baseline_1"},
  "steps": [
    {"type": "press", "button": "Up", "frames": 60},
    {"type": "wait", "seconds": 0.5},
    {"type": "assert", "address": "$7E008A", "notEquals": "prev", "description": "Screen changed"}
  ]
}
```

**Menu System Test** (`tests/menu_test.json`):
```json
{
  "name": "Menu Open/Close",
  "description": "Verify menu opens and closes properly",
  "saveState": {"id": "baseline_1"},
  "steps": [
    {"type": "press", "button": "Start", "frames": 5},
    {"type": "wait", "seconds": 0.5},
    {"type": "assert", "address": "$7E0010", "equals": 14, "description": "Menu mode"},
    {"type": "press", "button": "Start", "frames": 5},
    {"type": "wait", "seconds": 0.5},
    {"type": "assert", "address": "$7E0010", "equals": 9, "description": "Back to overworld"}
  ]
}
```

#### Task 2.2: Water Gate Regression Suite

Given current focus on water collision:

**Pre-fill State Test** (`tests/watergate/pre_fill_test.json`):
- Load state at room 0x27 entrance
- Verify water collision tiles not active
- Capture screenshot for baseline

**Post-fill State Test** (`tests/watergate/post_fill_test.json`):
- Trigger water gate switch
- Verify water collision active
- Capture screenshot

**Persistence Test** (`tests/watergate/persistence_test.json`):
- Exit and re-enter room 0x27
- Verify water state persists via `$7EF411`

---

### Phase 3: CI/CD Enhancement

#### Task 3.1: Create Mock Emulator for CI

Python module that simulates Mesen2 responses for offline testing.

```python
# tests/mocks/mock_mesen.py
class MockMesenBridge:
    def __init__(self, state_data: dict):
        self.memory = state_data.get("memory", {})

    def read_memory(self, address: int) -> int:
        return self.memory.get(address, 0)

    def write_memory(self, address: int, value: int):
        self.memory[address] = value
```

#### Task 3.2: Pytest Framework

```
tests/
├── unit/
│   ├── test_visual_diff.py
│   ├── test_state_library.py
│   ├── test_test_runner.py
│   └── conftest.py
├── integration/
│   ├── test_mesen_bridge.py
│   └── conftest.py
└── pytest.ini
```

---

### Phase 4: Metrics & Dashboard

#### Task 4.1: Test Result Storage

```json
// tests/results/history.json
{
  "runs": [
    {
      "timestamp": "2026-01-22T12:00:00Z",
      "romVersion": "oos168x",
      "commit": "abc123",
      "results": {
        "boot_test": "pass",
        "menu_test": "pass",
        "lr_swap_test": "skip"
      }
    }
  ]
}
```

#### Task 4.2: Dashboard Data Generator

Script to aggregate results and output JSON for `dashboard.html`:

```bash
python scripts/generate_dashboard_data.py --last 30
```

---

## 4. Immediate Action Items

### Today (Manual Setup)

1. [ ] Copy oos168x states to `Roms/SaveStates/library/baseline/`
2. [ ] Copy oos168x states to `Roms/SaveStates/library/oos168x/`
3. [ ] Update `save_state_library.json` with at least 3 entries
4. [ ] Capture 3 baseline screenshots (title, overworld, menu)

### This Week (Automation)

1. [ ] Create `state_import.py` helper script
2. [ ] Write 3 core test cases (boot, menu, transition)
3. [ ] Add pytest framework with 5+ unit tests
4. [ ] Document state capture workflow

### Future (Polish)

1. [ ] Implement mock emulator for CI
2. [ ] Add test metrics storage
3. [ ] Create dashboard data generator
4. [ ] Expand test coverage to 20+ scenarios

---

## 5. Testing Workflow Reference

### Creating a New Test

```bash
# 1. Identify scenario and required state
./scripts/mesen_cli.sh status  # Inspect current game state

# 2. Save state if needed
./scripts/mesen_cli.sh savestate 1

# 3. Export state to library
./scripts/state_library.py import --id "my_test_state" --slot 1

# 4. Create test definition
cat > tests/my_test.json << 'EOF'
{
  "name": "My Test",
  "saveState": {"id": "my_test_state"},
  "steps": [...]
}
EOF

# 5. Run test
python scripts/test_runner.py tests/my_test.json
```

### Running Full Test Suite

```bash
# All tests in tests/ directory
python scripts/test_runner.py "tests/*.json"

# Specific category
python scripts/test_runner.py "tests/watergate/*.json"

# With verbose output
python scripts/test_runner.py tests/my_test.json --verbose
```

### Visual Regression

```bash
# Capture baseline
./scripts/visual_diff.py capture --name water_gate_pre

# Later, verify against baseline
./scripts/visual_diff.py verify --name water_gate_pre --threshold 0.98

# Compare two images directly
./scripts/visual_diff.py compare before.png after.png --output diff.png
```

---

## 6. Appendix: Memory Address Reference

| Address | Name | Test Use |
|---------|------|----------|
| `$7E0010` | MODE | Boot/menu/game state verification |
| `$7E0011` | SUBMODE | Sub-state verification |
| `$7E001B` | INDOORS | Indoor/outdoor transitions |
| `$7E008A` | OWSCR | Overworld screen transitions |
| `$7E00A0` | ROOM | Dungeon room transitions |
| `$7E0739` | ACTIVE_ITEM | L/R swap verification |
| `$7EF342` | HOOKSHOT_SRAM | Item progression |
| `$7EF411` | WATER_GATE | Water persistence |
| `$7EF3C5` | GAME_STATE | Progression tracking |

---

## Summary

The infrastructure is **well-designed and nearly complete**. The primary blockers are **data gaps** (empty manifests, missing baselines), not code gaps. Filling these gaps requires:

1. **Manual state import** (~30 minutes)
2. **Screenshot capture session** (~20 minutes)
3. **Manifest population** (~1 hour)

After this foundation work, the full test automation pipeline can execute.
