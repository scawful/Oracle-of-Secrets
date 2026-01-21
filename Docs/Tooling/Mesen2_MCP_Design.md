# Mesen2 MCP Architecture Design

**Purpose**: Enable AI agents to debug Oracle of Secrets in real-time using Mesen2's debugger.
**Status**: Proposed Design

---

## 1. Overview

Mesen2 has a robust C++ debugger with the following capabilities:
- Memory read/write
- Breakpoint management (execute, read, write)
- CPU state inspection (registers, flags, stack)
- Disassembly
- Label management
- Expression evaluation

The goal is to expose these through an MCP server for use by Claude Code.

---

## 2. Architecture Options

### Option A: HTTP/REST Bridge (Recommended)

```
┌─────────────┐     HTTP      ┌─────────────┐
│ Claude Code │◀──────────────│  MCP Server │
│  (Client)   │               │  (Python)   │
└─────────────┘               └──────┬──────┘
                                     │ HTTP
                                     ▼
                              ┌─────────────┐
                              │  Mesen2 +   │
                              │  REST API   │
                              │  (Plugin)   │
                              └─────────────┘
```

**Pros**:
- Mesen2 already has Lua scripting support
- No need to modify Mesen2 core
- Easy to develop incrementally

**Cons**:
- Requires running a Lua script in Mesen2
- May have latency issues

### Option B: Shared Memory / IPC

```
┌─────────────┐     stdio     ┌─────────────┐
│ Claude Code │◀──────────────│  MCP Server │
│  (Client)   │               │   (C++)     │
└─────────────┘               └──────┬──────┘
                                     │ Shared Memory
                                     ▼
                              ┌─────────────┐
                              │   Mesen2    │
                              │   (Core)    │
                              └─────────────┘
```

**Pros**:
- Fastest possible communication
- Direct access to debugger APIs

**Cons**:
- Requires modifying Mesen2 source
- More complex to implement

### Option C: Mesen2 Plugin DLL

Use InteropDLL (already exists) as the bridge:

```
┌─────────────┐     stdio     ┌─────────────┐
│ Claude Code │◀──────────────│  MCP Server │
│  (Client)   │               │  (Python)   │
└─────────────┘               └──────┬──────┘
                                     │ FFI
                                     ▼
                              ┌─────────────┐
                              │ InteropDLL  │
                              │  (Mesen2)   │
                              └─────────────┘
```

**Pros**:
- InteropDLL already exposes debugger functions
- Well-documented interface

**Cons**:
- Requires Mesen2 to be running
- Python FFI complexity

---

## 3. Recommended Implementation: Option C (InteropDLL)

Mesen2's `InteropDLL/DebugApiWrapper.cpp` already exposes:

```cpp
// Memory operations
DllExport void __stdcall GetMemoryState(MemoryType type, uint8_t* buffer, uint32_t length);
DllExport void __stdcall SetMemoryValue(MemoryType type, uint32_t addr, uint8_t value);

// Breakpoints
DllExport void __stdcall SetBreakpoints(Breakpoint* breakpoints, uint32_t length);

// CPU state
DllExport void __stdcall GetState(BaseState* state, CpuType cpuType);
DllExport void __stdcall SetState(BaseState* state, CpuType cpuType);

// Execution control
DllExport void __stdcall Step(CpuType cpuType, int32_t count, StepType type);
DllExport bool __stdcall IsPaused();
DllExport void __stdcall Resume();
DllExport void __stdcall Pause();

// Disassembly
DllExport void __stdcall GetDisassembly(CpuType cpuType, uint32_t addr, ...);

// Evaluation
DllExport int64_t __stdcall EvaluateExpression(char* expression, CpuType cpuType, ...);
```

---

## 4. MCP Tool Specifications

### 4.1 Memory Operations

```python
@tool
def mesen2_read_memory(address: str, length: int = 1, memory_type: str = "WRAM") -> dict:
    """
    Read memory from the emulator.

    Args:
        address: Hex address (e.g., "7E0010" or "$7E0010")
        length: Number of bytes to read
        memory_type: WRAM, SRAM, ROM, VRAM, OAM, CGRAM

    Returns:
        {
            "address": "7E0010",
            "bytes": [0x00, 0x01, ...],
            "description": "Link X Position (if known)"
        }
    """

@tool
def mesen2_write_memory(address: str, values: list[int], memory_type: str = "WRAM") -> dict:
    """
    Write memory to the emulator.

    Args:
        address: Hex address
        values: List of byte values to write
        memory_type: Memory region type

    Returns:
        {"success": true, "address": "7E0010", "bytes_written": 2}
    """

@tool
def mesen2_watch_memory(address: str, length: int = 1, on_change: bool = True) -> dict:
    """
    Set up a memory watch.

    Returns:
        {"watch_id": 1, "address": "7E0010", "initial_value": [0x00]}
    """
```

### 4.2 Breakpoint Operations

```python
@tool
def mesen2_add_breakpoint(
    address: str,
    type: str = "EXECUTE",  # EXECUTE, READ, WRITE
    condition: str = None,  # Optional expression
    enabled: bool = True
) -> dict:
    """
    Add a breakpoint.

    Args:
        address: Hex address or label
        type: Breakpoint type
        condition: Expression like "A == $00"

    Returns:
        {"breakpoint_id": 1, "address": "028000", "type": "EXECUTE"}
    """

@tool
def mesen2_remove_breakpoint(breakpoint_id: int) -> dict:
    """Remove a breakpoint by ID."""

@tool
def mesen2_list_breakpoints() -> dict:
    """List all active breakpoints."""
```

### 4.3 Execution Control

```python
@tool
def mesen2_pause() -> dict:
    """Pause emulation."""

@tool
def mesen2_resume() -> dict:
    """Resume emulation."""

@tool
def mesen2_step(count: int = 1, type: str = "CPU") -> dict:
    """
    Step execution.

    Args:
        count: Number of steps
        type: CPU, PPU, FRAME

    Returns:
        {"pc": "028000", "instruction": "LDA $0010", "cycles": 4}
    """

@tool
def mesen2_step_over() -> dict:
    """Step over subroutine calls."""

@tool
def mesen2_step_out() -> dict:
    """Step out of current subroutine."""

@tool
def mesen2_run_to(address: str) -> dict:
    """Run until reaching a specific address."""
```

### 4.4 State Inspection

```python
@tool
def mesen2_get_cpu_state() -> dict:
    """
    Get current CPU state.

    Returns:
        {
            "pc": "028000",
            "a": 0x00,
            "x": 0x00,
            "y": 0x00,
            "sp": 0x01FF,
            "db": 0x02,
            "dp": 0x0000,
            "p": {
                "n": false, "v": false, "m": true, "x": true,
                "d": false, "i": false, "z": false, "c": false
            },
            "e": false
        }
    """

@tool
def mesen2_get_stack(depth: int = 16) -> dict:
    """
    Get stack contents.

    Returns:
        {"sp": 0x01FF, "stack": [0x00, 0x80, 0x02, ...]}
    """

@tool
def mesen2_get_disassembly(address: str, lines: int = 10) -> dict:
    """
    Get disassembly at address.

    Returns:
        {
            "address": "028000",
            "lines": [
                {"addr": "028000", "bytes": "A9 00", "asm": "LDA #$00"},
                ...
            ]
        }
    """
```

### 4.5 Expression Evaluation

```python
@tool
def mesen2_evaluate(expression: str) -> dict:
    """
    Evaluate an expression.

    Args:
        expression: "[$7E0010] == $00" or "A + X"

    Returns:
        {"expression": "[$7E0010]", "result": 42, "hex": "0x002A"}
    """
```

### 4.6 Oracle-Specific Tools

```python
@tool
def mesen2_get_link_state() -> dict:
    """
    Get Link's current state (Oracle-specific).

    Returns:
        {
            "position": {"x": 0x0100, "y": 0x0080},
            "state": "Walking",
            "direction": "South",
            "health": 6,
            "form": "Normal",
            "indoors": false,
            "area": 0x29
        }
    """

@tool
def mesen2_get_sprite_info(slot: int) -> dict:
    """
    Get sprite information for a slot.

    Returns:
        {
            "slot": 0,
            "type": "Darknut",
            "type_id": 0x1D,
            "position": {"x": 0x0100, "y": 0x0080},
            "health": 8,
            "action": 2,
            "active": true
        }
    """

@tool
def mesen2_get_game_mode() -> dict:
    """
    Get current game mode.

    Returns:
        {
            "mode": 0x09,
            "mode_name": "Overworld",
            "submodule": 0x00,
            "frame": 12345
        }
    """
```

---

## 5. Implementation Steps

### Phase 1: Basic Memory Access

1. Create Python MCP server skeleton
2. Load Mesen2's InteropDLL via ctypes
3. Implement `read_memory`, `write_memory`
4. Add Oracle-specific address descriptions

### Phase 2: Execution Control

1. Implement `pause`, `resume`, `step`
2. Implement breakpoint management
3. Add CPU state inspection
4. Test with basic debugging scenarios

### Phase 3: Oracle Integration

1. Add `get_link_state`, `get_sprite_info`
2. Integrate with Hyrule Historian for labels
3. Add expression evaluation with Oracle symbols
4. Create debugging workflow documentation

### Phase 4: Advanced Features

1. Memory watch with change detection
2. Callstack inspection
3. Trace logging integration
4. Conditional breakpoints with Oracle flags

---

## 6. Usage Example

```python
# Debugging a sprite crash

# 1. Set breakpoint on sprite prep
mesen2_add_breakpoint("Sprite_Booki_Prep", "EXECUTE")

# 2. Resume and wait for hit
mesen2_resume()
# ... player enters room with Booki ...

# 3. Inspect state at breakpoint
state = mesen2_get_cpu_state()
print(f"PC: {state['pc']}, A: {state['a']:02X}")

# 4. Check sprite slot
sprite = mesen2_get_sprite_info(0)
print(f"Sprite type: {sprite['type']}")

# 5. Step through prep routine
mesen2_step(10)

# 6. Read sprite RAM
ram = mesen2_read_memory("0D00", 16)  # SprY array
print(f"Sprite Y positions: {ram['bytes']}")

# 7. Continue execution
mesen2_remove_breakpoint(1)
mesen2_resume()
```

---

## 7. Alternative: CLI Integration with z3ed

The yaze CLI (z3ed) already has memory inspection capabilities. We could also:

1. Use z3ed's existing `memory_inspector_tool`
2. Build ROM diffing with z3ed's `rom_diff_tool`
3. Leverage z3ed's ALTTP memory map knowledge

This could complement Mesen2 for:
- Static ROM analysis
- Build verification
- Patch analysis

---

## 8. Implementation Status

**Completed** (see `Tools/mesen2_mcp/`):

1. [x] Evaluate InteropDLL function signatures
2. [x] Create Python ctypes bindings for Mesen2 (`mesen2_bridge.py`)
3. [x] Implement basic memory operations
4. [x] Add Oracle-specific helper functions (`get_link_state`, `get_sprite_info`, etc.)
5. [x] Create MCP server with all tools (`server.py`)
6. [x] Document debugging workflows (`README.md`)

**Remaining**:

1. [ ] Test with Oracle of Secrets ROM (requires compiled Mesen2)
2. [ ] Integrate with Hyrule Historian for symbol lookup
3. [ ] Add memory watch with change detection
4. [ ] Add trace logging integration
