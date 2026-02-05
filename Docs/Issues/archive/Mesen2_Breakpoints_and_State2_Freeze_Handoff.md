# Handoff: State 2 Freeze + Breakpoints (2026-01-29)

## Context
Goal: investigate freeze when loading Save State 2 (menu -> press A -> loads room 0x104 Link's House dungeon; yellow/green screen then freeze). User expects Oracle-of-Secrets custom code regression (last 1–2 months), not vanilla.

Key request: find Oracle namespace symbol / custom routine responsible. Also ensure Mesen2 OOS breakpoints work from socket.

## What was changed
**Mesen2 fork patch** to prevent socket breakpoints from being wiped by UI breakpoints:
- `Core/Debugger/Debugger.h`
- `Core/Debugger/Debugger.cpp`
- `Core/Shared/SocketServer.cpp`

Behavior: debugger now keeps two lists: `_userBreakpoints` (UI) and `_externalBreakpoints` (socket). `SetBreakpoints()` sets user list; new `SetExternalBreakpoints()` sets external list. `ApplyMergedBreakpoints()` merges both and pushes to BreakpointManager.

SocketServer `SyncBreakpoints()` now calls `SetExternalBreakpoints()` instead of `SetBreakpoints()`.

Built via `make` in `/Users/scawful/src/hobby/mesen2-oos` and deployed to `/Applications/Mesen2 OOS.app` by user.

## Current emulator state
- User relaunched `/Applications/Mesen2 OOS.app`.
- State 2 loaded (menu; pressing A loads file).
- Socket chosen: `/tmp/mesen2-72870.sock` (verify with health).

## Important tools
- `scripts/mesen2_client.py` uses the local socket bridge. Direct events can be flaky; use raw `MesenBridge` for CPU state.
- Use raw bridge with `PYTHONPATH=./scripts` to call commands directly.

Example:
```bash
PYTHONPATH=./scripts python3 - <<'PY'
import json
from mesen2_client_lib.bridge import MesenBridge
b = MesenBridge('/tmp/mesen2-72870.sock')
print(json.dumps(b.send_command('CPU'), indent=2))
PY
```

## Breakpoint verification
Breakpoints now fire when set via socket (confirmed). Example:
```python
b.send_command('BREAKPOINT', {'action':'add','addr':'0x0080C9','bptype':'exec'})
```
PC stops at 0x0080C9 (NMI entry). So socket breakpoints are working with new Mesen2.

## Repro flow (State 2)
1. Load state slot 2.
2. Press A (via CLI):
   `python3 scripts/mesen2_client.py --socket /tmp/mesen2-72870.sock press a --frames 8`
3. After load, game freezes with yellow/green screen bug.

## Observations
- PC sometimes ends at **0x00B7B8** or **0x1D66CC** during freeze.
  - 0x1D66CC is **invalid** in LoROM (bank 1D code should be at $1D:8000+), implies corrupted jump/stack.
- JumpTableLocal (`$00:8781`) gets hit when loading state 2.
  - CPU at hit: `PC=0x008781`, `A=0x0808`, `X=0x0000`, `Y=0x0000`, `SP=0x01EB`, `DBR=0x06`, `P=0xB0`.
  - Stack dump around SP shows return chain consistent with:
    - `0x06:84F3` (inside Sprite_ExecuteSingle right after JSL JumpTableLocal)
    - `0x02:8841` (after JSL Sprite_Main)
  - This suggests JumpTableLocal is being called from `Sprite_ExecuteSingle` as expected.

## New findings (2026-01-29)
- **Room 0x104 (Link's House) sprite list is vanilla-only** in the current ROM (`Roms/oos168x.sfc`):
  - `z3ed dungeon-list-sprites --room=0x104` reports a single sprite ID **0x33 (PullForRupees)**.
  - This makes a custom sprite main/prep routine unlikely as the root cause for the crash; focus on **Oracle hooks that run every frame or during palette/time/menu transitions**.
- **Most plausible Oracle root cause**: hook at `org $068361` → `Oracle.HUD_ClockDisplay` (`Overworld/time_system.asm`).
  - This hook runs **every frame** inside `Sprite_Main` just before the sprite dispatch loop.
  - Any P register leakage (especially X/Y size) here will cause `JumpTableLocal` to pop the wrong stack bytes.
- **High‑risk hook (pre‑patch)**: `Oracle.ColorBgFix` in `Overworld/time_system.asm` (`org $0ED5F9`).
  - It forced `SEP #$30` and did **not** restore P on exit, so X/Y could remain 8‑bit.
  - Fixed on 2026‑01‑29 via **PHP/PLP**.
- **Possible contributor**: `Menu_Exit` in `Menu/menu.asm` sets `REP #$20` and does not restore M.
  - On menu→file load→gameplay transitions, this can leave 16‑bit A active into the first `Sprite_Main` frame.
- **Systemic risk**: extended sprite dispatch (`Core/sprite_new_table.asm`) ends with `SEP #$30` before `JMP [$0006]`.
  - Any custom sprite calling `JSL JumpTableLocal` without reasserting `REP #$10` is vulnerable to stack corruption.

## Capture: State 2 → Link’s House (2026-01-29)
Socket: `/tmp/mesen2-72870.sock` (oos168x.sfc, crc32=03B56AD9)

### Breakpoint: $06:8361 (Oracle HUD hook inside Sprite_Main)
```
PC=068361  A=0140  X=0098  Y=000C  SP=01F0  K=06  DBR=06  P=31
Stack[01D0..] = 00000000000000000000000000000000000000000000000000000D0000A6016083004188021021000910210009598000
```
**P=0x31** → M=1, X=1 (A/X/Y 8‑bit). Index is already 8‑bit at the HUD hook.

### Breakpoint: $06:84E2 (Sprite_ExecuteSingle)
```
PC=0684E2  A=0001  X=000F  Y=0010  SP=01EE  K=06  DBR=06  P=30
Stack[01CE..] = 000000000000000000000000000000000000D0019BBA080348100037837BB7069BA68300418802102100091021000959
```
**P=0x30** → M=1, X=1 (A/X/Y 8‑bit).

### Breakpoint: $06:84F0 (JSL JumpTableLocal)
```
PC=0684F0  A=0808  X=0000  Y=0000  SP=01EE  K=06  DBR=06  P=B0
Stack[01CE..] = 000000000000000000000000000000000000D0019BBA40009BBA06168406EA8408A68300418802102100091021000959
```
**P=0xB0** → M=1, X=1 (Index 8‑bit). JumpTableLocal invoked with X/Y 8‑bit.

### Breakpoint: $00:8781 (JumpTableLocal)
```
PC=008781  A=0808  X=0000  Y=0000  SP=01EB  K=00  DBR=06  P=B0
Stack[01CB..] = 000000000000000000000000000000000000000000D0019BBA40009BBA06168406F38406A68300418802102100091021
```
**P=0xB0** confirms X/Y still 8‑bit at JumpTableLocal, matching the stack corruption hypothesis.


### Breakpoint: $34:83F4 (Oracle_ColorBgFix: STA TimeState_SubColor)
```
PC=3483F4  A=0000  X=00FF  Y=00FF  SP=01F4  K=34  DBR=00  P=02
Stack[01D4..] = 000000000000000000000000000000000000000000A40402FD8000A14FE8CE0000FCD50E36C60291825980000005000000000000000000000000000000000000
```
**P=0x02** → M=0, X=0 (A/X/Y 16‑bit) at the `STA TimeState_SubColor` inside `Oracle_ColorBgFix`.

Disasm confirms callsite and instruction:
- `$0E:D5F9` is `JSL Oracle_ColorBgFix` (`22 E8 83 34`).
- `$34:83F4` is `STA TimeState_SubColor` (`8F 18 E0 7E`).

### Pre‑patch: attempted break at ColorBgFix return (did not hit)
- Breakpoint at `$0E:D5FD` (return site after `JSL ColorBgFix`) did **not** trigger.
- CPU instead ends at **invalid PC 0x1D66CC** with corrupted stack, indicating the return address is already broken by this point.

## Isolation test (2026-01-29)
**Patch:** Temporarily replaced `org $068361` JSL target with vanilla `JSL $09B06E` (`22 6E B0 09`) via socket write.

**Result:** After reset → load state 2 → press A → advance 120 frames, CPU still ends at invalid PC **0x1D66CE**.

**Conclusion (pre‑patch):** Removing the HUD hook alone does **not** resolve the freeze; the P‑state leak likely occurs earlier (e.g., `ColorBgFix`, menu exit, or another global hook).

## Fix attempt: ColorBgFix preserves P (2026-01-29)
**Change:** `Overworld/time_system.asm` → `ColorBgFix` now wraps `PHP/PLP` and no longer forces `SEP #$30` on exit.

### Breakpoint: $0E:D5F9 (ColorBgFix callsite)
```
PC=0ED5F9  A=0000  X=0080  Y=00FF  SP=01F7  K=0E  DBR=00  P=13
Stack[01D7..] = 0000000000000000000000000000000000000000000E000032002B053B9E800BD4FAC5021C815980000000000000000000000000000000000000000000000000
```
**P=0x13** → M=0 (A 16‑bit), X=1 (index 8‑bit) at the callsite.

### Breakpoint: $0E:D5FD (return after JSL ColorBgFix)
```
PC=0ED5FD  A=0000  X=0010  Y=00FF  SP=01F7  K=0E  DBR=00  P=12
Stack[01D7..] = 000000000000000000000000000000000000A40402FD8000A14FFC833412FCD50E36C60291825980000005000000000000000000000000000000000000000000
```
**P=0x12** → M=0 restored at the return site (caller expects 16‑bit A for palette stores).

### Post‑patch outcome (prior run)
- Built ROM CRC32 **B678366E**.
- A prior run showed State 2 transitioning into **Dungeon (mode 7)** without the yellow/green freeze.
- This is **not confirmed** in the current repro; see “New evidence” below.

### New evidence (2026-01-29, later)
- PC hits **$83:A66D** and attempts `JSL $1D66CC` (invalid LoROM address).
- Stack return bytes decode to **$80:5909** (WRAM mirror), indicating **return-address corruption**.
- CPU snapshot at hit: `K=83`, `DBR=50`, `D=1009`, `P=00`, `SP=01FB`.
- Interpretation: **$83:A66D is a symptom** (executing data). Root cause is a prior Oracle routine that corrupts the stack or returns with the wrong width.

### Post‑patch sprite loop captures (stable)
```
PC=0684E2  A=00FF  X=000D  Y=0010  SP=01EE  K=06  DBR=06  P=30
```
```
PC=0684F0  A=0808  X=0000  Y=0000  SP=01EE  K=06  DBR=06  P=B0
```
```
PC=008781  A=0C00  X=00E0  Y=0000  SP=01F4  K=00  DBR=0C  P=32
```
Note: X remains 8‑bit in these captures, but the stack chain stays stable and no invalid PC occurs post‑patch.

## Where JumpTableLocal is called in this path
Vanilla (usdasm):
- `Sprite_ExecuteSingle` at `0x0684E2`
- `JSL JumpTableLocal` at `0x0684F0`
- `SpriteModule_Initialize` dispatch table at `0x068657` (JSL JumpTableLocal again) uses `$0E20,X` sprite ID.

## Breakpoints that were hit (post‑patch)
- `0x0ED5F9` (ColorBgFix callsite) hit in a dedicated pass.
- `0x0ED5FD` (return after `JSL ColorBgFix`) hit with **M=0** restored.
- `0x0684E2` (Sprite_ExecuteSingle) hit in dungeon state; `P=0x30` (M=1, X=1).
- `0x0684F0` (JSL JumpTableLocal) hit in dungeon state; `P=0xB0` (M=1, X=1).
- JumpTableLocal (`0x008781`) hit in dungeon state; `P=0x32` (M=1, X=1).

## Breakpoints that were hit (pre‑patch)
- `0x0684E2` (Sprite_ExecuteSingle) hit while loading state 2.
- `0x0684F0` (JSL JumpTableLocal) hit while loading state 2.
- JumpTableLocal (`0x008781`) hit after pressing A.
- `0x3483F4` (Oracle_ColorBgFix: `STA TimeState_SubColor`) hit during State 2 load.

## Breakpoints that did NOT hit (pre‑patch)
- `0x068657` (SpriteModule_Initialize -> JSL JumpTableLocal) did not hit before crash in one run, but may be timing-sensitive; retry.
- `0x0ED5FD` (return site after `JSL ColorBgFix`) did not trigger; CPU instead landed at invalid `0x1D66CC`.

## Hypothesis (updated)
`Oracle_ColorBgFix` **was** a viable mitigation (P preservation), but **stack corruption still occurs** in current repro. The priority is to identify the exact writer of the bogus return address bytes (`$01FC–$01FE`) via `MEM_WATCH_WRITES` + `MEM_BLAME`, then map that PC to an **Oracle** symbol and fix the mismatched JSL/RTL or missing P/DB/DP restore.

## Next agent: verification steps (current)
1) **Stack write attribution**: add `MEM_WATCH_WRITES` for `$01FC–$01FE`, reproduce State 2, then `MEM_BLAME` to identify the writer PC.
2) **Map to Oracle symbol** using `Roms/oos168x.mlb`, then audit that routine for JSL/RTL mismatch or missing `PLP/PLB`/stack balance.
3) **Confirm ROM parity**: disasm `Oracle_ColorBgFix` shows `PHP/PLP` and return at `$0E:D5FD` executes with **M=0**.
4) **Re‑run targeted breakpoints** (`$06:84E2`, `$06:84F0`, `$00:8781`) to ensure the stack chain remains stable under load.
5) **Run smoke/regression tests** and watch for palette regressions (HUD/background colors during transitions).

## Files of interest
- `Overworld/time_system.asm` (HUD_ClockDisplay hook)
- `Menu/menu.asm` (Menu_Exit P state)
- `Menu/menu_hud.asm` (HUD hooks)
- `Core/sprite_new_table.asm` (extended dispatch ends with SEP #$30)
- `Core/sprite_functions.asm`, `Core/sprite_macros.asm`, `Sprites/NPCs/*`
- Hooks near `0x068361` in custom ASM

## Commands used
- Load state: `python3 scripts/mesen2_client.py --socket /tmp/mesen2-72870.sock load 2`
- Press A: `python3 scripts/mesen2_client.py --socket /tmp/mesen2-72870.sock press a --frames 8`
- CPU state (raw):
```bash
PYTHONPATH=./scripts python3 - <<'PY'
import json
from mesen2_client_lib.bridge import MesenBridge
b = MesenBridge('/tmp/mesen2-72870.sock')
print(json.dumps(b.send_command('CPU'), indent=2))
PY
```
- Read stack block:
```python
b.send_command('READBLOCK', {'addr':'0x0001DB','len':'48'})
```

## Notes
- `mesen2_client.py disasm` sometimes fails to resolve PC (returns 0); use raw bridge `CPU` command instead.
- `subscribe` command in mesen2_client currently broken (keyword mismatch), avoid.
- TRACE buffer fetch via socket returned empty `entries` even when enabled; may require fork-side investigation.
