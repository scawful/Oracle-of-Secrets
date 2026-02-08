# Emulator Infra Spec (Bridge + Reinit Hooks)

**Date:** 2026-01-22
**Scope:** Oracle-of-Secrets emulator/debug/test infrastructure
**Focus:** (1) Bridge spec + capability map + selftest harness, (3) runtime reinit hooks + RPC mapping

---

## 0) Goals (Accuracy First)
- Deterministic, repeatable behavior across Mesen2/Yaze/Z3ed.
- Preflight capability validation before any test run.
- Safe control surface (no blind byte pokes).
- Clear, machine-parseable logs + human-readable summaries.
- Save-state stability with explicit post-load normalization.

## 1) Bridge 2.0 Spec (Transport + RPC)

### 1.1 Transport
### 1.1 Transport
- **Primary:** Unix Domain Socket (C++ SocketServer implementation).
- **Protocol:** JSON messages (Line-delimited).
- **Status:** **Implemented** (replaces legacy file polling).

### 1.2 Versioning / Handshake
- `bridge.hello` returns:
  - `bridge_version`, `protocol_version`
  - `instance_id`
  - `emu.name`, `emu.version`
  - `rom.hash`, `rom.path`, `rom.title`
  - `script_hash` (Lua script file hash)
  - `capabilities` (list)

### 1.3 Capability Map
- On startup, bridge emits `capabilities.json` (per instance):
  - `timestamp`, `bridge_version`, `protocol_version`
  - `emu` info
  - `rom.hash`
  - `capabilities`: `{name, status, details}`
- Tests **must fail fast** if required caps are missing.

### 1.4 Core RPC Methods (Mesen2)
Minimal set to unblock deterministic testing:

**State**
- `state.get` -> returns normalized state object
- `state.keys` -> list of supported state paths
- `state.has` -> check path existence

**Memory**
- `mem.read` (addr, size, domain)
- `mem.write` (addr, bytes, domain)
- `mem.readblock` / `mem.writeblock`

**Input**
- `input.press` (buttons, frames)
- `input.release`

**Save/Load**
- `savestate.save` (slot | path)
- `savestate.load` (slot | path)
- `savestate.status` (progress, errors)

**Screenshots**
- `screen.capture` (path, format)

**Timing**
- `emu.pause`, `emu.resume`
- `emu.step` (frames)

**Debug** (if supported)
- `dbg.breakpoint.add/remove/list`
- `dbg.stacktrace`
- `dbg.disasm` (pc range)

**Reinit (new)**
- `reinit.queue` (list of reinit targets)
- `reinit.status` (per-target result codes)

### 1.5 Normalized State Schema
Must be stable across emulators:
- `mode`, `submode`, `indoors`, `roomId`
- `link.x`, `link.y`, `link.dir`, `link.state`
- `rng.seed` (if available)
- `frame`
- `bridge.instance_id`

### 1.6 Selftest Harness
- `bridge.selftest` runs at startup and on demand.
- Each test outputs **pass/fail** + message.
- Example tests:
  - `state.get` returns required keys
  - `mem.read/write` round-trip on test buffer
  - `savestate.save/load` works (optional)
  - `screen.capture` returns file
  - `emu.pause/step/resume` works (optional)
- Results recorded in `capabilities.json`.

### 1.7 Preflight Rules (Host Side)
- CLI refuses to run any test unless required caps are **pass**.
- Each test declares its requirements in metadata:
  - `requires: [state.get, mem.read, savestate.load, screen.capture]`

---

## 2) Runtime Reinit Hooks (ASM + RPC)

### 2.1 Problem Statement
Save-states can leave **stale runtime caches** (dialog pointer tables, sprite tables, overlays). We need **safe, deterministic reinit** at known points, without full reboot.

### 2.2 Reinit Targets (Initial Set)
- `reinit.dialog` -> reload dialogue dictionary pointer tables
- `reinit.sprites` -> rebuild sprite tables / sprite init state
- `reinit.overlays` -> reapply overworld overlays / map gfx tables
- `reinit.msgbank` -> reload message bank if swapped
- `reinit.roomcache` -> invalidate room cache / collision overlay

### 2.3 Scheduling Model
- **Bridge writes flags** to a WRAM debug region.
- The game checks these flags at **safe points** and performs reinit:
  - **Preferred:** during VBlank/NMI-safe update step
  - **Fallback:** early in `Module_MainRouting` when `MODE` is stable

### 2.4 WRAM Contract
Finalized in `Docs/Agent/Reinit_Hooks_Spec.md`:
- `DBG_REINIT_FLAGS`  = `$7E0746` (bitfield) -> requested reinit targets
- `DBG_REINIT_STATUS` = `$7E0747` (bitfield) -> completed targets
- `DBG_REINIT_ERROR`  = `$7E0748` (bitfield) -> failed targets
- `DBG_REINIT_SEQ`    = `$7E0749` (byte)     -> increment on each request
- `DBG_REINIT_LAST`   = `$7E074A` (byte)     -> last executed target

### 2.5 ASM Implementation Skeleton
- `Oracle_ReinitDispatcher`:
  - `PHP`, `PHB` -> set known bank + 8-bit
  - if `!DBG_REINIT_FLAGS == 0` -> exit
  - call target-specific routines
  - update status bits + clear flags
  - `PLB`, `PLP`, `RTL`

### 2.6 Hook Placement
**Chosen (debug build):** per-frame hook in `Util/item_cheat.asm` at `org $068365`  
See `Docs/Agent/Reinit_Hooks_Spec.md` for gating rules and rationale.

### 2.7 RPC Mapping
- `reinit.queue`:
  - inputs: list of targets (strings)
  - bridge maps to bits in `!DBG_REINIT_FLAGS`
  - increments `!DBG_REINIT_SEQ`
- `reinit.status`:
  - reports `flags`, `status`, `error`, `seq`

### 2.8 Safety Rules
- All reinit routines must:
  - preserve P/X/M flags (`PHP/PLP`, `SEP/REP`)
  - avoid long DMA / VRAM updates unless in VBlank
  - be **idempotent** (can run multiple times)

---

## 3) Implementation Plan (High-Level)

### Phase A: Bridge Spec + Capabilities
- JSON-RPC schema + capability names (`Docs/Agent/Emulator_Infra_RPC.md`).
- Implement `bridge.hello` + `bridge.selftest`.
- Emit `capabilities.json` per instance.

### Phase B: Reinit Hooks
- Add `Dungeons/Debug/reinit.asm` (name TBD) with dispatcher + targets.
- WRAM debug block allocated at `$7E0746` (see `Core/symbols.asm`).
- Hook `Oracle_ReinitDispatcher` at `org $068365` (debug build).

### Phase C: RPC Mapping
- Implement `reinit.queue` and `reinit.status` in bridge.
- Add CLI helpers: `mesen_cli.sh reinit dialog,sprites`.

### Phase D: Validation
- Contract tests for `reinit.queue` and status transitions.
- Save-state load + reinit + state validation script.

---

## 4) Open Questions (Need User Decision)
- Preferred transport: socket vs file-poll?
- Should reinit hooks be gated by a build flag (debug-only)?

---

## 5) Immediate Next Outputs (No Test Runs)
- Detailed reinit hook spec (`Docs/Agent/Reinit_Hooks_Spec.md`).
- Capability list + selftest matrix.
