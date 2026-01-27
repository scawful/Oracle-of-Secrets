# Runtime Reinit Hooks Spec (Draft)

**Date:** 2026-01-22
**Scope:** Safe runtime reinitialization after save-state load
**Status:** Draft (no tests run)

---

## 0) Goals
- Prevent stale caches after save-state load (dialog pointers, sprite tables, overlays).
- Expose deterministic reinit via bridge RPC (`reinit.queue`, `reinit.status`).
- Keep routines safe: idempotent, short, and scheduler-driven.

## 1) Reinit Targets (Initial Set)
| Bit | Target | Purpose | Notes |
| --- | ------ | ------- | ----- |
| 0 | `dialog` | Reload dialogue dictionary pointer tables | Avoid stale message pointers |
| 1 | `sprites` | Rebuild sprite tables / sprite init state | Avoid corrupt sprite state |
| 2 | `overlays` | Reapply overworld overlays / map gfx tables | Keep OW visuals consistent |
| 3 | `msgbank` | Reload message bank if swapped | Safety for custom message banks |
| 4 | `roomcache` | Invalidate room cache / collision overlay | Prevent partial collision maps |

(Additional bits reserved for future use.)

## 2) WRAM Debug Block (Final)
We need a small, stable WRAM block for reinit requests + status.

**Chosen location:** custom WRAM region (`$7E0730+`, MAP16OVERFLOW free RAM).

```
DBG_REINIT_FLAGS  = $7E0746  ; requested targets (bitfield)
DBG_REINIT_STATUS = $7E0747  ; completed targets (bitfield)
DBG_REINIT_ERROR  = $7E0748  ; failed targets (bitfield)
DBG_REINIT_SEQ    = $7E0749  ; increments each request
DBG_REINIT_LAST   = $7E074A  ; last executed target (optional)
DBG_WARP_ARM      = $7E074B  ; debug warp arm byte (must be set to 0xA5)
```

**Rationale:** $7E0224 is actively used by dungeon floor tags. The $7E0730+ region is the project’s designated custom WRAM block and has unused space after $7E0745.

## 3) Scheduling Model
- Bridge sets `DBG_REINIT_FLAGS` and increments `DBG_REINIT_SEQ`.
- Game checks flags at safe points and executes targets.
- After completion: update `STATUS`, clear `FLAGS`.

**Safe points (candidates):**
- Post-module routing, before heavy rendering.
- Overworld/Underworld main loop (skip menu and intro).
- Optional: after save-state load hook if we add one.

**Rule:** only run reinit routines when not in the middle of NMI/VRAM updates.

## 4) ASM Dispatcher (Skeleton)
```asm
Oracle_ReinitDispatcher:
{
  PHP
  PHB
  PHK : PLB           ; set data bank
  SEP #$30            ; 8-bit A/X

  LDA.l DBG_REINIT_FLAGS : BEQ .done

  ; Example: dialog
  LDA.l DBG_REINIT_FLAGS : AND #$01 : BEQ .skip_dialog
    JSL Oracle_Reinit_DialogPointers
    LDA.l DBG_REINIT_STATUS : ORA #$01 : STA.l DBG_REINIT_STATUS
  .skip_dialog

  ; repeat per bit...

  STZ.l DBG_REINIT_FLAGS

.done
  PLB
  PLP
  RTL
}
```

## 5) Target Routine Map (Concrete)
These map directly to known routines already in the project/vanilla:

- **dialog** → `CreateMessagePointers` (`$0ED3EB`)  
  Defined in `Util/item_cheat.asm` and used in `Debug_ReloadRuntimeCaches`.

- **sprites** → `Sprite_LoadGraphicsProperties` (`$00FC41`) plus sprite reload:  
  - Overworld: `Sprite_ReloadAll_Overworld` (`$09C499`)  
  - Underworld: `Debug_LoadUnderworldSprites` wrapper (`$3CB000`), which calls `Underworld_LoadSprites` (`$09C290`)

- **overlays** → `Overworld_ReloadSubscreenOverlay_Interupt` (`$02AF58`)  
  Only when `MODE==Overworld` and not in mirror warp submodes.

- **msgbank** → alias to `CreateMessagePointers` (`$0ED3EB`)  
  (No separate bank-reset routine identified yet; pointer rebuild is the safe default.)

- **roomcache** → `CustomRoomCollision` (`$258000`, called at `$01B95B`)  
  **Guarded:** only run during underworld load/transition submodes (e.g. `Module07_01_IntraroomTransition`, `Module07_02_InterroomTransition`, `Module06_UnderworldLoad`). If not in a safe submode, set `DBG_REINIT_ERROR` and defer.

**Safe submode list (current, conservative):**
- `MODE=0x06` (Module06_UnderworldLoad)
- `MODE=0x07` + `SUBMODE=0x01` (IntraroomTransition)
- `MODE=0x07` + `SUBMODE=0x02` (InterroomTransition)
- `MODE=0x07` + `SUBMODE=0x1A` (RoomDraw_OpenTriforceDoor_bounce)

Each routine must be **idempotent**, **short**, and **safe** to run multiple times.

## 6) Hook Location (Final)
**Chosen:** per-frame debug hook already in `Util/item_cheat.asm`  
`org $068365 : JSL $3CA62A` (runs every frame).

Add `JSL Oracle_ReinitDispatcher` near the top of the routine with gating:
- `MODE` must be `0x07` or `0x09`
- `SUBMODE` must be stable gameplay (not transition/menu)
- `INDOORS` used to select OW/UW sprite reload routine

This keeps reinit isolated to debug builds and avoids touching the main game loop until validated.

**Implementation location:** `Util/item_cheat.asm` (bank $3C, `org $3CB200`).

## 7) RPC Mapping (Bridge)
- `reinit.queue` → map target strings to bits → set flags → increment seq.
- `reinit.status` → read flags/status/error/seq and return JSON.

Example `reinit.queue` params:
```json
{"targets": ["dialog", "sprites"]}
```

Example `reinit.status` result:
```json
{"flags": "0x03", "status": "0x03", "error": "0x00", "seq": 12}
```

## 8) Safety Rules
- Preserve processor state in every reinit routine (`PHP/PLP`, `SEP/REP`).
- Avoid long DMA / VRAM updates unless in VBlank.
- Never call reinit during menu/intro unless explicitly allowed.

## 9) Build Flags (Optional)
- Gate this system behind a build flag, e.g. `!DEBUG_REINIT = 1`.
- When disabled, dispatcher is a no-op.

## 10) Open Decisions
- Which underworld submodes are safe for `roomcache` reinit.
- Whether to promote the hook into non-debug builds after validation.

---

## Immediate Next Step (No Tests)
- Decide safe underworld submodes for `roomcache` reinit.
- Add dispatcher ASM stub + hook in debug build.
- Wire `reinit.queue`/`reinit.status` in bridge after ASM exists.
