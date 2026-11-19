# Goriya Sprite Analysis

This document describes the `Sprites/Enemies/goriya.asm` sprite (`$2C` / `Sprite_Goriya`), including its properties, AI state machine, boomerang projectile behavior, alternate palette system, and OAM drawing routines.

## 1. Sprite Properties

```asm
!SPRID              = Sprite_Goriya
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful
!Health             = 08  ; 8 HP (also enforced in Sprite_Goriya_Prep)
!Damage             = 00
!Hitbox             = 00
```

`Sprite_Goriya_Prep` initializes `SprHealth` to `$08` and assigns the instance's OAM palette bits (`palette << 1`) in `SprMiscG`:
- **Subtypes `2..6`** explicitly select **Red** (`$06`, Pal 3), **Blue** (`$08`, Pal 4; Teal in DW), **Green** (`$0A`, Pal 5), **Sand** (`$0C`, Pal 6), or **Gold** (`$02`, Pal 1).
- **Default subtype `0`** alternates by sprite slot parity (`TXA : AND #$01`):
  - **Desert (`$1B == 0`, OW `$36`)**: Sand (`$0C`, Pal 6) and Red (`$06`, Pal 3).
  - **Elsewhere**: Classic Red (`$06`, Pal 3) and Classic Blue (`$08`, Pal 4; Teal in DW).

## 2. Core Routines

### 2.1. `Sprite_Goriya_Long`
- Skips drawing when `SprState == $06` (vanilla death poof).
- Dispatches `SprSubtype == $01` to `Sprite_Boomerang_Draw`; all Goriya variants (`0` and `2+`) run `Sprite_Goriya_Draw` + `Sprite_DrawShadow`.
- Calls `Sprite_Goriya_Main` when `Sprite_CheckActive` returns carry set.

### 2.2. `Sprite_Goriya_Main` & `Sprite_Goriya_Move`
- **Action dispatch**:
  - `SprSubtype == $01` jumps to `BoomerangAttack`.
  - Goriya (`SprAction` `0..3`: Up, Down, Left, Right) routes through `Goriya_WalkAnim` and `Sprite_Goriya_Move`.
- **Animation snapping (`Goriya_SyncFrame`)**: Keeps `SprFrame` aligned to `[SprAction*2, SprAction*2 + 1]` on direction changes and holds the standing pose (`SprAction << 1`) while waiting for the thrown boomerang (`SprMiscB == 4`).
- **Detection & Chase**:
  - `Goriya_IsPlayerWithinRange` uses 16-bit absolute X/Y delta checks against `!Goriya_DetectRange` (`$68` px) without 256 px page wrap glitches.
  - Taking damage (`Sprite_CheckDamageFromPlayer`) or spotting Link refreshes `SprTimerE` (`!Goriya_AlertDuration = $60`), raising speed from `GoriyaMovementSpeed` (`12`) to `!Goriya_ChaseSpeed` (`16`) and steering via `Sprite_DirectionToFacePlayer` mapped through `Goriya_FaceToDir` (`db $03, $02, $01, $00`).
- **Tile Collision (`Goriya_HandleTileCollision`)**:
  - Shared with `Sprites/Enemies/darknut.asm`.
  - On collision, picks a random direction guaranteed to differ from the current `SprAction`, writes it to `SprAction`, `SprMiscB`, and `SprMiscE`, and sets `SprTimerC` to `60`.

### 2.3. `Goriya_BoomerangAttack` & `BoomerangAttack`
- When alerted (`SprTimerE != 0`), cooldown ready (`SprTimerD == 0`), and Link is within `!Goriya_ThrowRange` (`$78`), Goriya pauses (`SprMiscB = 4`, `SprTimerC = $48`, `SprTimerD = $90`), faces Link, plays `SFX2.09`, and spawns child `SprSubtype = 1`, `SprAction = 4` via `Sprite_SpawnDynamically`.
- Child boomerang sets `SprNbrOAM = $00` (1 tile), `$0E60 = $40` (`ImperviousAll`), `SprDefl = $56` (deflects arrows/sword/projectiles), `SprTileDie = $01`, `SprBulletproof = $FF`, `SprMiscA` = parent slot, and flies outward at speed `!Goriya_BoomSpeed` (`$20`) for `!Goriya_BoomOutTime` (`$28`) frames.
- Hitting Link, clinking off a weapon, hitting a wall, or expiring `SprTimerD` calls `Boomerang_StartReturn` (`SprMiscC = 1`, `SprTimerD = $38`, `Sprite_InvertSpeed_XY`).
- On return, if the parent Goriya slot in `SprMiscA` is still active and within `!Goriya_CatchDist` (`12` px) on the same page, the boomerang despawns and cuts the parent's `SprTimerC` pause to `1`.

### 2.4. `Sprite_Goriya_Draw` & `Sprite_Boomerang_Draw`
- Both guard with `JSL Sprite_PrepOamCoord : BCC .on_screen` before allocating OAM.
- `Sprite_Goriya_Draw` clears hardcoded palette bits from `.properties` (`$21` / `$61`) and computes `$08 = ((SprFlash << 1) ^ SprMiscG) & $0E` so alternate palettes and damage flash cycling work cleanly without disturbing nametable or priority bits.
- `Sprite_Boomerang_Draw` renders the single rotating tile (`$26`, properties `$22/$A2/$E2/$62`) directly without table-loop overhead.
