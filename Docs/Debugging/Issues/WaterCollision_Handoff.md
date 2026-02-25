# Water Collision + Water Gate (Zora Temple) Handoff

**Created:** 2026-02-07
**Status:** Active (needs runtime verification)

This document is the current, minimal, technical truth for the Zora Temple water-gate system: what code is involved, what it is supposed to do, and how to test it without guesswork.

## Follow-up Patch (2026-02-16)

Applied data-driven fixes for active Zora Baby + water gate regressions:

- `Sprites/NPCs/followers.asm`
  - Added switch-trigger debounce in `ZoraBaby_GlobalBehavior` (only trigger in actions `0` or `4`).
  - Added room-based post-switch target lookup (`ZoraBabySwitchTargetTable`) and movement routine (`ZoraBaby_RunPostSwitchSequence`) so the baby can walk toward room-authored markers before follower handoff.
  - Target selection is runtime-nearest among all authored markers for the current room.
  - `ZoraBaby_PostSwitch` now runs the movement sequence instead of immediately snapping to follow.
- `Dungeons/dungeons.asm`
  - Removed hardcoded water overlay blob.
  - Added table-driven selector `WaterGate_SelectOverlayPointer` and switched `org $01CBAC` to `JSL` selector + `JSR RoomTag_OperateWaterFlooring`.
  - Overlay data now comes from generated tables (`Dungeons/generated/water_gate_runtime_tables.asm`) instead of manual patch bytes.
- `scripts/generate_water_gate_runtime_tables.py` (new)
  - Extracts room overlay object streams (default object ids `0xC9,0xD9`) and Zora Baby switch targets from ROM room data.
- `scripts/build_rom.sh`
  - Auto-runs table generation before assembly, preferring `Oracle-of-Secrets.yaze` `rom_filename` as source ROM.

Runtime expectations to verify:

- Throwing Zora Baby onto switch should show one message and not loop infinitely.
- Zora Baby should walk briefly toward the room marker target after switch interaction, then return to follower flow.
- Room overlay segments are generated from room-authored objects (default ids `0xC9`/`0xD9`) and selected per-room at runtime.

## Yaze Authoring Controls

Use these room-data controls to drive runtime behavior without hand-editing ASM:

- Water drain/gate overlay segments:
  - Place water overlay objects in the room (`0x0C9` flood and/or `0x0D9` swim-mask forms).
  - Build regenerates `WaterOverlayRoomTable` automatically.
- Zora Baby post-switch walk target:
  - Place one marker object near the desired destination using ids in priority order:
    - `0x0124` (preferred)
    - `0x0137`
    - `0x0135`
  - Build regenerates `ZoraBabySwitchTargetTable`; baby picks the nearest marker at runtime.
- Water fill collision zones (switch-activated):
  - Paint custom collision tile `0xF5` in the room where water should become swimmable after switch activation.
  - `CustomRoomCollision` now treats `0xF5` as an authoring marker and does **not** apply it during normal room load.
  - Build regenerates `Dungeons/generated/water_fill_table.asm` (ROM `$25:E000`) from those marker offsets.
  - At water fill completion, runtime writes deep-water collision (`0x08`) to those offsets.
  - Preset-driven CLI workflow (recommended):
    - `python3 scripts/water_fill_author.py --rom Roms/oos168x.sfc --preset zora_d4 --write`
    - Presets:
      - `room25_lower_band` (lower-half drain band)
      - `room27_upside_t` (dam upside-T with right-side stair gap)
      - `zora_d4` (applies both)

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
    - `org $0188DF` -> kept vanilla (`db $D0,$E8`) to avoid transition corruption
    - `org $01CBAC` -> overlay data redirect (feature-gated)
  - Data include:
    - `incsrc "Dungeons/generated/water_gate_runtime_tables.asm"`
- `Sprites/NPCs/followers.asm`
  - Zora Baby follower logic that pulls the relevant switch sprites.
- `scripts/generate_water_gate_runtime_tables.py`
  - Generates room overlay + Zora Baby target tables from ROM dungeon data.
- `scripts/generate_water_fill_table.py`
  - Generates runtime water-fill table from `0xF5` markers in room custom collision data.
- `scripts/water_fill_author.py`
  - Applies room presets for marker painting via `z3ed` with readback validation.

## Feature Flags

From `Config/feature_flags.asm`:

- `!ENABLE_WATER_GATE_HOOKS`
  - Controls the fill-complete hook.
- `!ENABLE_WATER_GATE_ROOMENTRY_RESTORE` (**default OFF**)
  - Enables water-gate persistence restore (re-apply collision on room entry when SRAM bit is set).
  - Implementation is **room-load safe**: called from `CustomRoomCollision` (`org $01B95B`) after collision streaming completes.
- `!ENABLE_WATER_GATE_OVERLAY_REDIRECT`
  - Controls whether room tag overlay flooring reads from generated room-authored tables.

If you are debugging a regression, isolate by turning these off one at a time.

## Persistence / SRAM

SRAM byte: `WaterGateStates` at **`$7EF411`** (defined in `Core/sram.asm`).

- bit 0: room `0x27`
- bit 1: room `0x25`

The fill-complete hook sets the bit for the current room after applying collision.
Room entry re-applies collision if the bit is set.

## What The System Actually Does

### 0) Build-time table generation

- Script: `python3 scripts/generate_water_gate_runtime_tables.py --rom <rom>`
- Script: `python3 scripts/generate_water_fill_table.py --rom <rom>`
- Auto-run during build (`scripts/build_rom.sh`) unless `OOS_SKIP_WATER_TABLE_GEN=1`.
- Outputs:
  - `WaterOverlayRoomTable` / `WaterOverlayData_*` (from object ids `0xC9,0xD9` by default)
  - `ZoraBabySwitchTargetTable` (marker priority default: `0x124,0x137,0x135`)
  - `WaterFillTable_Generated` at `$25:E000` (from custom collision marker tile `0xF5`)

### 1) When the water fill animation completes

Hook: `WaterGate_FillComplete_Hook` (installed at `org $01F3D2` in `Dungeons/dungeons.asm`).

- Runs original replaced code (`STZ $1E/$1F` + `IrisSpotlight_ResetTable`).
- Checks current room (`$A0`).
- For room `0x27` or `0x25`:
  - selects a collision offset table (`WaterGate_Room27_Data` / `WaterGate_Room25_Data`)
  - writes deep-water collision (`$08`) into both layers (`$7F2000` and `$7F3000`)
  - sets the persistence bit in SRAM

### 2) Overlay selection at runtime

- `RoomTag_WaterGate` (`org $01CBAC`) calls `WaterGate_SelectOverlayPointer`.
- Selector scans `WaterOverlayRoomTable` for current room `$A0`.
- If no entry exists, it falls back to `WaterOverlayData_Empty`.

### 3) When entering the room later (persistence)

Implementation:
- Persistence restore runs during room load via `CustomRoomCollision` (`org $01B95B`) when `!ENABLE_WATER_GATE_ROOMENTRY_RESTORE = 1`.
- The old global torch-loop hook at `$0188DF` is no longer installed (site is kept vanilla).

`WaterGate_CheckRoomEntry`:
- If room is `0x27` and bit0 is set: sets `$0403 = 2` (skip animation) and reapplies collision.
- If room is `0x25` and bit1 is set: sets `$0403 = 2` and reapplies collision.

### 4) Collision placement gotcha (why offsets look too low)

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

0. **Choose persistence strategy**
- Default build (recommended): keep `!ENABLE_WATER_GATE_ROOMENTRY_RESTORE = 0` to avoid dungeon blackout corruption.
- If you need to test legacy persistence restore anyway: build with `--enable water_gate_roomentry_restore` and only test in Zora Temple rooms.

1. **Room 0x27 gate fill**
- Trigger the switch/fill.
- After animation completes, verify swim area collision behaves correctly.
- Leave the room and re-enter.
- Expected: collision state persists (no need to re-trigger fill).
  - Note: requires a persistence mechanism. The legacy mechanism is currently disabled by default.

2. **Room 0x25 grate open**
- Trigger the grate open.
- Verify collision changes (new swim area).
- Leave/re-enter.
- Expected: collision state persists.
  - Note: requires a persistence mechanism. The legacy mechanism is currently disabled by default.

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
