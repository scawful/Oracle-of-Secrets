# Mesen2 Debug Integration Backlog

**Created:** 2026-01-24
**Status:** Active Development
**Owner:** Agentic Debugging Infrastructure Team

---

## Overview

This backlog tracks integration work between the Mesen2 fork (Oracle of Secrets debugging) and agentic harnesses (YAZE, Claude skills, Python automation). Tasks are prioritized by impact on debugging workflows.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| P0 | Critical - Blocks core functionality |
| P1 | High - Major feature enablement |
| P2 | Medium - Quality of life improvement |
| P3 | Low - Nice to have |

---

## Backlog

### P0 - Critical

#### 1. Fix Mesen2 Fork Socket Server Stability
**Type:** Manual (requires debugging, testing)
**Status:** Blocked - intermittent crashes

**Description:**
Socket server crashes on some script executions, preventing automated state capture.

**Steps to Investigate:**
1. Review `Core/Shared/SocketServer.cpp` crash handling
2. Add more defensive parsing in `ParseCommand()`
3. Test with simplified script payloads
4. Check memory allocation in response building

**Files:**
- `Core/Shared/SocketServer.cpp`
- `Core/Shared/SocketServer.h`

**Acceptance Criteria:**
- Socket server handles malformed requests gracefully
- No crashes during 100+ consecutive commands
- Error responses returned for invalid requests

---

#### 2. Complete Tier 2 Black Screen Smoke Testing
**Type:** Manual (requires visual verification)
**Status:** Pending

**Description:**
Visual pass/fail testing with vanilla Mesen.app to verify theoretical fixes.

**Test Matrix:**
| Test Case | Action | Expected | Result |
|-----------|--------|----------|--------|
| OW→Cave | Walk into cave entrance | Fade transition, cave loads | [ ] |
| OW→Dungeon | Enter Graveyard dungeon | Spotlight, room loads | [ ] |
| OW→Building | Enter Kakariko house | Screen transition | [ ] |
| Dungeon Stairs (inter) | Room change stairs | New room loads | [ ] |
| Dungeon Stairs (intra) | Layer change stairs | Same room, different layer | [ ] |
| Dungeon→OW | Exit dungeon | Return to overworld | [ ] |

**How to Test:**
```bash
open /Applications/Mesen.app
# Load Roms/oos168x.sfc
# Navigate and test each scenario
```

**Acceptance Criteria:**
- All 6 scenarios documented with PASS/FAIL
- Any FAIL includes Mode/Sub/INIDISP values
- Screenshots captured for failures

---

### P1 - High Priority

#### 3. Wire YAZE Save State to MCP Bridge
**Type:** Automated (code implementation)
**Status:** Partial - Proto exists, bridge missing

**Description:**
YAZE proto already has `SaveState`, `LoadState`, `ListStates` RPCs in `emulator_service.proto`. Need to verify implementation and expose via MCP bridge.

**Implementation:**
1. Verify `SaveState`/`LoadState` RPCs work in yaze_grpc_service.cc
2. Add wrappers to yaze-mcp bridge
3. Add CLI commands for manual testing

**Files:**
- `~/src/hobby/yaze/src/protos/emulator_service.proto` - **DONE** (has SaveState, LoadState, ListStates)
- `~/src/hobby/yaze/src/app/service/yaze_grpc_service.cc` - Verify implementation
- `~/src/tools/yaze-mcp/` (bridge updates needed)

**Proto Details (Already Defined):**
```protobuf
rpc SaveState(SaveStateRequest) returns (SaveStateResponse);
rpc LoadState(LoadStateRequest) returns (LoadStateResponse);
rpc ListStates(ListStatesRequest) returns (ListStatesResponse);
```

**Acceptance Criteria:**
- gRPC calls succeed for save/load
- MCP bridge exposes state management
- CLI: `yaze state save <path>` and `yaze state load <path>`

---

#### 4. Populate Save State Library
**Type:** Manual (requires gameplay)
**Status:** Partial (manifest exists, states missing)

**Description:**
State library manifest at `Docs/Testing/save_state_library.json` has 22 entries but `.mss` files may be missing.

**State Types Needed:**
| Type | Count | Purpose |
|------|-------|---------|
| baseline | 4 | Fresh game starts |
| overworld | 8 | Key OW locations |
| dungeon | 6 | Dungeon test points |
| boss | 2 | Boss encounters |
| transition | 2 | Pre-transition captures |

**How to Capture:**
```bash
# With Mesen2 running
python3 scripts/mesen2_client.py capture
# Or via socket API
echo '{"type":"SAVESTATE","slot":"1"}' | nc -U /tmp/mesen2-*.sock
```

**Acceptance Criteria:**
- All 22 manifest entries have corresponding `.mss` files
- States load without errors
- Metadata (area, room, link position) matches manifest

---

#### 5. Implement Breakpoint Profiles
**Type:** Automated (code implementation)
**Status:** Not Started

**Description:**
Add preset breakpoint configurations for common debug scenarios.

**Profiles Needed:**
| Profile | Breakpoints | Purpose |
|---------|-------------|---------|
| transition | $02D8EB, $0289BF, $028364 | Area transitions |
| sprite_spawn | $05C66E, $05C612 | Sprite creation |
| collision | $07D077, $07CF8C | Collision detection |
| mode_change | $7E0010 write | Game mode tracking |

**Implementation:**
1. Add `BREAKPOINT_PROFILES` dict to `mesen2_client.py`
2. Add `breakpoint --profile transition` CLI command
3. Test each profile with known scenarios

**Files:**
- `scripts/mesen2_client_lib/client.py`
- `scripts/mesen2_client_lib/cli.py`

**Acceptance Criteria:**
- `python3 scripts/mesen2_client.py breakpoint --profile transition` works
- Breakpoints trigger at expected addresses
- Can enable/disable profiles

---

### P2 - Medium Priority

#### 6. Research Bird Travel Camera Mechanism
**Type:** Research (analysis required)
**Status:** Not Started

**Description:**
Cross-area warps leave camera misconfigured. Bird travel properly handles this.

**Research Tasks:**
1. Trace `BirdTravel_LoadTargetArea_Interupt` at $0AB8F5
2. Document camera boundary setup ($0600-$0606)
3. Identify which functions set scroll registers
4. Compare bird travel vs mosaic transition flow

**Files:**
- `Overworld/ZSCustomOverworld.asm`
- USDASM `bank_0A.asm`

**Output:**
- Document in `Docs/Technical/camera_setup.md`

---

#### 7. Agent Session Logging + Action Attribution
**Type:** Automated (code implementation)
**Status:** Not Started

**Description:**
Create a lightweight session log that records all CLI actions, run-state transitions, and whether inputs were agent- or user-driven.

**Implementation Ideas:**
1. Add `--log <path>` to `mesen2_client.py` (or env var) to append JSONL per command.
2. Capture timestamp, command, params, socket path, run/paused state, and labels used.
3. Optional helper to summarize the log for handoff docs.

**Files:**
- `scripts/mesen2_client_lib/cli.py`
- `scripts/mesen2_client_lib/client.py`

**Acceptance Criteria:**
- `--log` writes JSONL entries for each command.
- Log contains run/paused state before/after input commands.
- Quick summary option produces a markdown snippet for scratchpad.

---

#### 8. Deep Diagnostics Snapshot (Items/Flags/Sprites)
**Type:** Automated (code implementation)
**Status:** Done (2026-01-25)

**Description:**
Extend diagnostics to include items, flags, sprites, and watch profile values for agent debugging insight.

**Acceptance Criteria:**
- `python3 scripts/mesen2_client.py diagnostics --deep --json` includes items, flags, sprites, watch profile, and watch values.
- Agent command `python3 scripts/mesen2_client.py agent diagnostics --deep` returns same payload.

---

#### 9. Black Screen / Crash Detector
**Type:** Automated (code implementation)
**Status:** Not Started

**Description:**
Detect black-screen conditions automatically during overworld traversal tests.

**Implementation Ideas:**
1. Add `detect_black_screen()` to compare screenshot histogram or INIDISP values.
2. Add `overworld_coverage` runner that warps + walks in each area and flags failures.
3. Save a labeled state + screenshot when failure is detected.

**Files:**
- `scripts/mesen2_client_lib/client.py`
- `scripts/mesen2_client_lib/cli.py`
- `scripts/overworld_explorer.py` (if present)

**Acceptance Criteria:**
- CLI command reports PASS/FAIL per area.
- Failures include save state label + screenshot path.

---

#### 10. Dedicated Diagnostics Output Window (Mesen2 UI)
**Type:** UI (code implementation)
**Status:** Not Started

**Description:**
Provide an in-app window/popup to display ZSCustomOverworld + Day/Night diagnostic output instead of launching external tools.

**Implementation Ideas:**
1. Add an Avalonia window with a read-only text log.
2. Trigger gateway actions and render output in the window.
3. Add a "Copy to clipboard" and "Save log" buttons.

**Files:**
- `UI/Windows/OracleDiagnosticsWindow.axaml` (new)
- `UI/ViewModels/OracleDiagnosticsViewModel.cs` (new)
- `UI/ViewModels/MainMenuViewModel.cs`

**Acceptance Criteria:**
- Oracle menu "Diagnostics" opens in-app output window.
- Output is captured without external console dependency.
- Propose fix for warp system

---

#### 7. Fix Cross-Area Warp Camera
**Type:** Automated (code fix)
**Status:** Blocked by #6

**Description:**
Apply camera fix based on bird travel research.

**Current State:**
- Same-area teleports: Working
- Cross-area warps: Reach destination, camera wrong
- Dungeon warps: Disabled (too complex)

**Files:**
- `Util/item_cheat.asm` - WarpDispatcher, WarpPostTransitionCheck

---

#### 8. Enable Automated Regression Tests
**Type:** Automated (infrastructure)
**Status:** Partial

**Description:**
Wire `test_runner.py` to use socket API for automated testing.

**Current State:**
- `scripts/test_runner.py` exists
- Socket API has all needed commands
- No automated test suite defined

**Steps:**
1. Define test cases in `scripts/tests/`
2. Add state library integration
3. Add assertion framework
4. Wire to CI workflow

**Acceptance Criteria:**
- `python3 scripts/test_runner.py --suite regression` runs tests
- Tests use save state library for setup
- Results logged to `Docs/Testing/results/`

---

### P3 - Low Priority

#### 9. Add Conditional Watch Triggers
**Type:** Automated (Mesen2 enhancement)
**Status:** Not Started

**Description:**
Notify on specific memory value changes (e.g., Mode == 0x07 AND INIDISP == 0x80).

**Implementation:**
- Add to `MEM_WATCH_WRITES` command
- Support `condition` parameter with expression

---

#### 10. Execution Profiling (Hotspot Analysis)
**Type:** Automated (Mesen2 enhancement)
**Status:** Not Started

**Description:**
Track which addresses are executed most frequently.

**Use Case:**
- Find performance bottlenecks
- Identify code paths during bugs

---

#### 11. Symbol File Hot Reload
**Type:** Automated (Mesen2 enhancement)
**Status:** Not Started

**Description:**
Automatically reload `.sym` file when ROM is rebuilt.

**Current Behavior:**
- Symbols loaded once at ROM load
- Requires restart to update

---

## Completed Tasks

| Task | Completion Date | Notes |
|------|-----------------|-------|
| P_WATCH/P_LOG/P_ASSERT | 2026-01-24 | Commit f22c1c23 |
| MEM_WATCH_WRITES/MEM_BLAME | 2026-01-24 | Commit f22c1c23 |
| Frame-based INPUT injection | 2026-01-24 | Commit 73441358 |
| BATCH command | 2026-01-23 | Socket API extension |
| GAMESTATE/SPRITES | 2026-01-23 | ALTTP game state reading |
| COLLISION_OVERLAY | 2026-01-23 | Visualize collision maps |

---

## Dependencies

```
   P0.1 (Socket Stability)
         |
         v
   P0.2 (Tier 2 Testing) <-- Manual, no code deps
         |
         v
   P1.4 (State Library) <-- Requires stable socket
         |
         v
   P1.5 (Breakpoint Profiles)
         |
         v
   P2.8 (Regression Tests)
         |
         v
   P2.7 (Warp Camera) <-- P2.6 Research
```

---

*Last updated: 2026-01-24*
