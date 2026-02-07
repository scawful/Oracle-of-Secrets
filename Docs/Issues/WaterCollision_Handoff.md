# Water Collision + Water Gate (Zora Temple) Handoff

**Created:** 2026-02-07
**Status:** Active (needs runtime verification)

This document is the current, minimal, technical truth for the Zora Temple water-gate system: what code is involved, what it is supposed to do, and how to test it without guesswork.

## Scope

- Zora Temple rooms:
  - **Room `0x27`**: water gate fill (swim area becomes deep water).
  - **Room `0x25`**: water grate opens (swim area collision changes).
- Collision writes into the underworld collision tilemaps (`$7F2000`/`$7F3000`).
- Persistence across room re-entry and save/load using SRAM.

## Files / Entry Points

- `Dungeons/Collision/water_collision.asm`
  - `WaterGate_FillComplete_Hook`
  - `WaterGate_ApplyCollision`
  - `WaterGate_SetPersistenceFlag`
  - `WaterGate_CheckRoomEntry`
  - `Underworld_LoadRoom_ExitHook` (torch-loop exit hook that calls `WaterGate_CheckRoomEntry`)
- `Dungeons/dungeons.asm`
  - Hooks:
    - `org $01F3D2` -> `WaterGate_FillComplete_Hook` (feature-gated)
    - `org $0188DF` -> `Underworld_LoadRoom_ExitHook` (feature-gated)
    - `org $01CBAC` -> overlay data redirect (feature-gated)
- `Sprites/NPCs/followers.asm`
  - Zora Baby follower logic that pulls the relevant switch sprites.

## Feature Flags

From `Config/feature_flags.asm`:

- `!ENABLE_WATER_GATE_HOOKS`
  - Controls the fill-complete hook and the room-load persistence hook.
- `!ENABLE_WATER_GATE_OVERLAY_REDIRECT`
  - Controls whether room tag overlay flooring reads from `NewWaterOverlayData`.

If you are debugging a regression, isolate by turning these off one at a time.

## Persistence / SRAM

SRAM byte: `WaterGateStates` at **`$7EF411`** (defined in `Core/sram.asm`).

- bit 0: room `0x27`
- bit 1: room `0x25`

The fill-complete hook sets the bit for the current room after applying collision.
Room entry re-applies collision if the bit is set.

## What The System Actually Does

### 1) When the water fill animation completes

Hook: `WaterGate_FillComplete_Hook` (installed at `org $01F3D2` in `Dungeons/dungeons.asm`).

- Runs original replaced code (`STZ $1E/$1F` + `IrisSpotlight_ResetTable`).
- Checks current room (`$A0`).
- For room `0x27` or `0x25`:
  - selects a collision offset table (`WaterGate_Room27_Data` / `WaterGate_Room25_Data`)
  - writes deep-water collision (`$08`) into both layers (`$7F2000` and `$7F3000`)
  - sets the persistence bit in SRAM

### 2) When entering the room later (persistence)

Hook: `Underworld_LoadRoom_ExitHook` (installed at `org $0188DF`).

- It must preserve the vanilla torch-loop behavior and register state.
- On the vanilla fallthrough path, it calls `WaterGate_CheckRoomEntry` (JSL) and returns.

`WaterGate_CheckRoomEntry`:
- If room is `0x27` and bit0 is set: sets `$0403 = 2` (skip animation) and reapplies collision.
- If room is `0x25` and bit1 is set: sets `$0403 = 2` and reapplies collision.

### 3) Collision placement gotcha (why offsets look too low)

Vanilla collision checks for swimming/water are not at Link's visual center. The deep-water detect path uses an offset (~+20 px Y), so collision data must be placed **2-3 tiles below** where Link appears to stand.

This is why `WaterGate_Room27_Data` is defined in the Y=41-44 band even if the water looks like it is around Y=39-40.

## Zora Baby Follower Integration (Water Dam / Gate)

Zora Baby is implemented as the Locksmith sprite (`0x39`) with a follower AI hook.

- Follower type: `0x09` (see `Sprites/NPCs/followers.asm`)
- Every frame while active, the Zora Baby checks for:
  - Water-gate switch sprite type `0x04`
  - Generic pull switch sprite type `0x21`

When standing on the water gate switch, it:

- faces upward toward the switch
- forces a switch gfx state (`SprGfx = 0x0D` for the switch slot)
- sets `[$0642] = 1` (water gate tag trigger value)
- transitions to `ZoraBaby_PullSwitch`

This is the expected trigger path for starting the water fill/grate sequence.

## Runtime Verification Checklist (What To Test)

Minimum tests (must pass on the same ROM build):

1. **Room 0x27 gate fill**
- Trigger the switch/fill.
- After animation completes, verify swim area collision behaves correctly.
- Leave the room and re-enter.
- Expected: collision state persists (no need to re-trigger fill).

2. **Room 0x25 grate open**
- Trigger the grate open.
- Verify collision changes (new swim area).
- Leave/re-enter.
- Expected: collision state persists.

3. **Save/load persistence**
- Save after opening/filling.
- Hard reset / reload.
- Re-enter rooms 0x25 and 0x27.
- Expected: collision is still correct and animation is skipped (`$0403=2` path).

4. **Regression: dungeon transitions**
- Enter/exit Zora Temple multiple times after these changes.
- Expected: no black screen, no stuck fade.

Suggested instrumentation via the socket client:

- Watch `INIDISP` (`$2100`) while transitioning.
- Watch `GameMode` and `SubMode` to confirm module transitions.
- Watch `WaterGateStates` (`$7EF411`) to confirm bits set.

## Known Failure Modes / Guardrails

- **Hook ABI / register-width leakage:** Any hook touching `REP/SEP` must restore `P` (or explicitly re-establish expected width) before returning to vanilla.
- **Torch loop contract:** `Underworld_LoadRoom_ExitHook` must not `SEP` on the torch-loop branch (`JML $0188C9`), because vanilla runs that loop in 16-bit mode.
- **Visual vs collision mismatch:** If Link appears to stand in water but cannot swim, adjust collision offsets, not the visual water.
