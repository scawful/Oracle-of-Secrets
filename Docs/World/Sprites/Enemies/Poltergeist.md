# Poltergeist Sprite Analysis

This document provides a detailed analysis of the `poltergeist.asm` sprite, outlining its properties, core routines, and behavioral patterns.

## 1. Sprite Properties

The following `!SPRID` constants define Poltergeist's fundamental characteristics:

```asm
!SPRID              = Sprite_PolsVoice
!NbrTiles           = 02  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 10  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 00  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss
```
**Note:** `!Health` is set to `10` and is dynamically determined during initialization based on Link's sword level.

## 2. Core Routines

### 2.1. `Sprite_Poltergeist_Long` (Main Loop)

This is the primary entry point for Poltergeist's per-frame execution. It handles drawing, shadow rendering, and then dispatches to the main logic routine if the sprite is active.

```asm
Sprite_Poltergeist_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Poltergeist_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Poltergeist_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

### 2.2. `Sprite_Poltergeist_Prep` (Initialization)

This routine is executed once when Poltergeist is first spawned. It sets its health based on Link's sword level and initializes `SprTimerA` and `SprTimerB`.

```asm
Sprite_Poltergeist_Prep:
{
  PHB : PHK : PLB
  LDA.l Sword : DEC A : TAY
  LDA.w .health, Y : STA.w SprHealth, X
  LDA.b #$80 : STA.w SprTimerA, X
  LDA.b #$80 : STA.w SprTimerB, X
  PLB
  RTL

  .health
    db $06, $0A, $0C, $10
}
```

### 2.3. `Sprite_Poltergeist_Main` (Behavioral State Machine)

This routine manages Poltergeist's AI through a state machine, using `SprAction, X` to determine its current behavior. It includes states for moving, attacking, and being stunned.

```asm
Sprite_Poltergeist_Main:
{
  JSL Sprite_DamageFlash_Long

  %SpriteJumpTable(Poltergeist_Move,
                   Poltergeist_Attack,
                   Poltergeist_Stunned)

  Poltergeist_Move:
  {
    %PlayAnimation(0, 1, 16)
    JSR Sprite_Poltergeist_Move
    RTS
  }

  Poltergeist_Attack:
  {
    %PlayAnimation(2, 3, 16)
    JSL Sprite_Move
    JSL Sprite_CheckDamageToPlayer
    LDA.w SprTimerA, X : BNE + ; If timer A is not 0
      %GotoAction(0) ; Transition back to Poltergeist_Move
    +
    RTS
  }

  Poltergeist_Stunned:
  {
    %PlayAnimation(4, 5, 16)
    JSL Sprite_Move
    JSL Sprite_CheckDamageToPlayer
    LDA.w SprTimerA, X : BNE + ; If timer A is not 0
      %GotoAction(0) ; Transition back to Poltergeist_Move
    +
    RTS
  }
}
```

### 2.4. `Sprite_Poltergeist_Move` (Movement Logic)

This routine handles Poltergeist's movement patterns, including moving towards Link, bouncing from tile collisions, and changing direction randomly.

```asm
Sprite_Poltergeist_Move:
{
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_CheckIfRecoiling

  LDA.w SprTimerC, X : BNE ++ ; Check timer C
    JSL GetRandomInt : AND #$3F : BNE ++ ; Random chance to change direction
      LDA.b #$40 : STA.w SprTimerC, X
      JSL Sprite_SelectNewDirection
  ++

  LDA.w SprTimerA, X : BNE + ; Check timer A
    JSL Sprite_IsToRightOfPlayer : CPY.b #$01 : BNE .ToRight
      %GotoAction(1) ; Transition to Poltergeist_Attack
      JMP .Continue
    .ToRight
    %GotoAction(1) ; Transition to Poltergeist_Attack
    LDA.b #$20 : STA.w SprTimerA, X
    JMP .Continue
  +
  %GotoAction(0) ; Transition to Poltergeist_Move
  .Continue

  LDA.w SprMiscB, X
  JSL JumpTableLocal

  dw PoltergeistMove

  PoltergeistMove:
  {
    JSL GetRandomInt : AND.b #$03
    JSL Sprite_ApplySpeedTowardsPlayer
    JSL Sprite_CheckTileCollision

    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer

    RTS
  }
}
```

### 2.5. `Sprite_Poltergeist_Draw` (Drawing Routine)

This routine is responsible for rendering Poltergeist's graphics. It uses the `%DrawSprite()` macro, which reads from a set of data tables to handle its multi-tile appearance and animation.

```asm
Sprite_Poltergeist_Draw:
{
  %DrawSprite()

  .start_index
    db $00, $03, $06, $09, $0C, $0F
  .nbr_of_tiles
    db 2, 2, 2, 2, 2, 2
  .x_offsets
    dw 0, 0, 8
    dw 8, 0, 0
    dw 0, 0, 8
    dw 0, 0, 8
    dw 0, 8, 0
    dw 0, 8, 0
  .y_offsets
    dw -8, 0, -8
    dw -8, 0, -8
    dw 0, -8, -8
    dw 0, -8, -8
    dw 0, -8, -8
    dw 0, -8, -8
  .chr
    db $3A, $02, $3B
    db $3A, $02, $3B
    db $20, $00, $01
    db $22, $10, $11
    db $20, $00, $01
    db $22, $10, $11
  .properties
    db $2B, $2B, $2B
    db $6B, $6B, $6B
    db $2B, $2B, $2B
    db $2B, $2B, $2B
    db $6B, $6B, $6B
    db $6B, $6B, $6B
  .sizes
    db $00, $02, $00
    db $00, $02, $00
    db $02, $00, $00
    db $02, $00, $00
    db $02, $00, $00
    db $02, $00, $00
}
```

## 3. Key Behaviors and Implementation Details

*   **Dynamic Health:** Poltergeist's health is determined at spawn time based on Link's current sword level, allowing for dynamic difficulty scaling.
*   **State Management:** Poltergeist uses `SprAction, X` and `%SpriteJumpTable` to manage its `Poltergeist_Move`, `Poltergeist_Attack`, and `Poltergeist_Stunned` states. Transitions between these states are triggered by timers and player proximity.
*   **Movement Patterns:** Poltergeist moves towards Link (`Sprite_ApplySpeedTowardsPlayer`) with random direction changes (`Sprite_SelectNewDirection`). It also handles bouncing from tile collisions and cannot be passed through by Link.
*   **Attack Behavior:** Poltergeist transitions to an `Poltergeist_Attack` state, which likely involves a direct contact attack or a projectile, and then returns to its movement state after a timer.
*   **Stunned State:** When damaged, Poltergeist enters a `Poltergeist_Stunned` state, during which it is temporarily incapacitated. It recovers from this state after a timer.
*   **Conditional Invulnerability:** The sprite properties indicate `!ImpervSwordHammer = 00`, but the code does not explicitly set it to `01` when stunned. This might be an oversight or handled by a global routine. However, the presence of `SprDefl` in `_Prep` suggests some form of deflection is intended.
*   **Custom OAM Drawing:** Poltergeist uses the `%DrawSprite()` macro with detailed OAM data tables to render its multi-tile appearance and animations across its different states.
*   **`SprTimerA`, `SprTimerB`, `SprTimerC` Usage:** These timers control the duration of attack and stunned states, and the frequency of direction changes.
