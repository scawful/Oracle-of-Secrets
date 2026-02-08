# Mesen2 Debugging Enhancements Plan

This plan outlines the implementation of advanced debugging features for the `mesen2-oos` integration, focusing on bridging the gap between Python scripts and Lua emulator internals.

## Phase 1: Unified Debugging API (Convergence)
- [x] **Extend Lua Bridge**: Added `CALLSTACK`, `LABELS`, `REGISTERS`, and `HUD_SET` support.
- [x] **Update Python Client**: Implemented `get_callstack`, `get_labels`, `disassemble`, `get_cpu_state`, `execute_lua`, and event waits.
- [x] **Symbolic Resolution**: Python API now handles label-to-address conversion.

## Phase 2: Real-time Debug HUD & Overlays
- [x] **Lua HUD Implementation**: Created `mesen_hud.lua` with sprite boxes and player info.
- [x] **Remote Toggles**: Added `HUD_SET` command to Lua bridge.

## Phase 3: Advanced Inspection Tools
- [x] **Snapshot & Diff**: Created `scripts/ram_inspector.py` with symbolic resolution.
- [ ] **Symbolic Tracing**: Update tracing logic to include labels.

## Phase 4: Reliability & AI Integration
- [x] **Event-Driven Synchronization**: Added `wait_for_label` and `wait_for_value`.
- [ ] **Automated Crash Dumps**:
- [ ] **Rolling Time-Travel**: 


## Phase 5: Verification & Testing
- [ ] **Test Runner Upgrade**: Update `test_runner.py` to use event-driven waits.
- [ ] **Regression Tests**: Add tests for the new debugging API itself.
