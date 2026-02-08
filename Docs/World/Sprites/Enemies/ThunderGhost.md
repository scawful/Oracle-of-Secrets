# Thunder Ghost Sprite Analysis

This document provides a detailed analysis of the `thunder_ghost.asm` sprite, outlining its properties, core routines, and behavioral patterns.

## 1. Sprite Properties

The following `!SPRID` constants define Thunder Ghost's fundamental characteristics:

```asm
!SPRID              = Sprite_ThunderGhost
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 10  ; Number of Health the sprite have (dynamically set in _Prep)
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 09  ; 00 to 31, can be viewed in sprite draw tool
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
**Note:** `!Health` is initially set to `10` but is dynamically determined during initialization based on Link's sword level.

## 2. Core Routines

### 2.1. `Sprite_ThunderGhost_Long` (Main Loop)

This is the primary entry point for Thunder Ghost's per-frame execution. It handles drawing, shadow rendering (conditionally), and then dispatches to the main logic routine if the sprite is active.

```asm
Sprite_ThunderGhost_Long:
{
  PHB : PHK : PLB
  JSR Sprite_ThunderGhost_Draw
  LDA.w SprAction, X : CMP.b #$03 : BCS + ; Don't draw shadow if casting thunder
    JSL Sprite_DrawShadow
  +
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_ThunderGhost_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

### 2.2. `Sprite_ThunderGhost_Prep` (Initialization)

This routine is executed once when Thunder Ghost is first spawned. It sets its health based on Link's sword level and initializes `SprTimerA` and `SprTimerB`.

```asm
Sprite_ThunderGhost_Prep:
{
  PHB : PHK : PLB
  LDA.l Sword : DEC A : TAY
  LDA.w .health, Y : STA.w SprHealth, X ; Set health based on sword level
  LDA.b #$08 : STA.w SprTimerB, X
  LDA.b #$08 : STA.w SprTimerA, X
  PLB
  RTL

  .health
    db $06, $0A, $0C, $10 ; Health values for each sword level
}
```

### 2.3. `Sprite_ThunderGhost_Main` (Behavioral State Machine)

This routine manages Thunder Ghost's AI through a state machine, using `SprAction, X` to determine its current behavior. It includes states for facing forward, left, and right, as well as states for casting thunder in different directions.

```asm
Sprite_ThunderGhost_Main:
{
  %SpriteJumpTable(ThunderGhostFaceForward,
                   ThunderGhostLeft,
                   ThunderGhostRight,
                   CastThunderLeft,
                   CastThunderRight)

  ThunderGhostFaceForward:
  {
    %PlayAnimation(0, 1, 16)
    JSR Sprite_ThunderGhost_Move
    RTS
  }

  ThunderGhostLeft:
  {
    %PlayAnimation(2, 3, 16)
    JSR Sprite_ThunderGhost_Move
    RTS
  }

  ThunderGhostRight:
  {
    %PlayAnimation(4, 5, 16)
    JSR Sprite_ThunderGhost_Move
    RTS
  }

  CastThunderLeft:
  {
    %StartOnFrame(6)
    %PlayAnimation(6, 6, 16)
    JSL Sprite_CheckDamageToPlayer
    JSL Sprite_MoveLong

    LDA.w SprTimerA, X : BNE + ; If timer A is not 0
      STZ.w SprState, X       ; Clear sprite state (despawn?)
    +
    RTS
  }

  CastThunderRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(7, 7, 16)

    JSL Sprite_CheckDamageToPlayer
    JSL Sprite_MoveLong

    LDA.w SprTimerA, X : BNE + ; If timer A is not 0
      STZ.w SprState, X       ; Clear sprite state (despawn?)
    +
    RTS
  }
}
```

### 2.4. `Sprite_ThunderGhost_Move` (Movement and Interaction Logic)

This routine handles Thunder Ghost's movement, collision, and interaction with the player. It also includes logic for randomly triggering lightning attacks and changing its facing direction.

```asm
Sprite_ThunderGhost_Move:
{
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckIfRecoiling
  LDA.w SprTimerC, X : BNE ++ ; Check timer C
    JSL GetRandomInt : AND #$3F : BNE ++ ; Random chance to spawn lightning
      LDA.b #$40 : STA.w SprTimerC, X ; Set timer C
      JSR SpawnLightningAttack       ; Spawn lightning attack
  ++

  LDA.w SprTimerA, X : BNE + ; Check timer A
    JSL Sprite_IsToRightOfPlayer : CPY.b #$01 : BNE .ToRight ; Determine if to the right of Link
      %GotoAction(1) ; Transition to ThunderGhostLeft
      JMP .Continue
    .ToRight
    %GotoAction(2) ; Transition to ThunderGhostRight
    LDA.b #$20 : STA.w SprTimerA, X ; Set timer A
    JMP .Continue
  +
  %GotoAction(0) ; Transition to ThunderGhostFaceForward
  .Continue

  LDA.w SprMiscB, X
  JSL JumpTableLocal

  dw ThunderGhostMove

  ThunderGhostMove:
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

### 2.5. `SpawnLightningAttack`

This routine is responsible for spawning the lightning attack sprite. It sets up the lightning's initial properties, including its `SprSubtype`, action, position, and speed, based on Thunder Ghost's position relative to Link.

```asm
SpawnLightningAttack:
{
  PHX
  LDA.b #$CD ; Sprite ID for lightning (assuming $CD is the lightning sprite ID)
  JSL Sprite_SpawnDynamically : BMI .no_space
    ; Use SprXSpeed, SprYSpeed, SprXRound, SprYRound
    ; SprX, SprY, SprXH, SprY, to cast the lightning spell
    ; and make it move off to the bottom left or bottom right

    ; Y is the ID of the new attack sprite
    ; X is the ID of the current source sprite

    ; Left 0 or Right 1
    PHY
    JSL Sprite_IsToRightOfPlayer : TAY : CMP.b #$01 : BEQ + ; Determine if to the right of Link
      LDA.b #$00
      JMP .Continue
    +
    LDA.b #$01
    .Continue
    CLC : ADC.b #$03
    PLY
    STA.w SprSubtype, Y ; Set SprSubtype for lightning
    STA.w SprAction, Y  ; Set action for lightning

    LDA.w SprX, X : STA.w SprX, Y
    LDA.w SprY, X : STA.w SprY, Y
    LDA.w SprXH, X : STA.w SprXH, Y
    LDA.w SprYH, X : STA.w SprYH, Y

    LDA.w SprXSpeed, X : STA.w SprXSpeed, Y
    LDA.w SprYSpeed, X : STA.w SprYSpeed, Y
    LDA.b #$02 : STA.w SprXRound, Y
    LDA.b #$02 : STA.w SprYRound, Y
    LDA.b #$30 : STA.w SprTimerA, Y
    LDA.b #$30 : STA.w SprTimerB, Y
  .no_space

  PLX

  RTS
}
```

### 2.6. `Sprite_ThunderGhost_Draw` (Drawing Routine)

This routine is responsible for rendering Thunder Ghost's graphics. It uses the `%DrawSprite()` macro, which reads from a set of data tables to handle its multi-tile appearance and animation.

```asm
Sprite_ThunderGhost_Draw:
{
  %DrawSprite()

  .start_index
  db $00, $03, $06, $09, $0C, $0F, $12, $15
  .nbr_of_tiles
  db 2, 2, 2, 2, 2, 2, 2, 2
  .x_offsets
  dw 0, 0, 8
  dw 8, 0, 0
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 8, 0
  dw 0, 8, 0
  dw -12, -8, -16
  dw 12, 16, 20
  .y_offsets
  dw -8, 0, -8
  dw -8, 0, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 12, 24, 20
  dw 12, 24, 12
  .chr
  db $3A, $02, $3B
  db $3A, $02, $3B
  db $20, $00, $01
  db $22, $10, $11
  db $20, $00, $01
  db $22, $10, $11
  db $28, $2A, $2B
  db $28, $2A, $2B
  .properties
  db $2B, $2B, $2B
  db $6B, $6B, $6B
  db $2B, $2B, $2B
  db $2B, $2B, $2B
  db $6B, $6B, $6B
  db $6B, $6B, $6B
  db $2B, $2B, $2B
  db $6B, $2B, $2B
  .sizes
  db $00, $02, $00
  db $00, $02, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
}
```

## 3. Key Behaviors and Implementation Details

*   **Dynamic Health:** Thunder Ghost's health is determined at spawn time based on Link's current sword level, allowing for dynamic difficulty scaling.
*   **Conditional Shadow Drawing:** The shadow is not drawn when Thunder Ghost is in its `CastThunderLeft` or `CastThunderRight` states, suggesting a visual distinction during its attack.
*   **Lightning Attack:** Thunder Ghost has a random chance to spawn a lightning attack (`SpawnLightningAttack`) at regular intervals, which then becomes an independent sprite with its own movement and interaction logic.
*   **State Management:** Thunder Ghost uses `SprAction, X` and `%SpriteJumpTable` to manage its facing direction (forward, left, right) and its thunder-casting states.
*   **Movement Patterns:** Thunder Ghost moves randomly and applies speed towards the player, while also bouncing from tile collisions and being unable to be passed through by Link.
*   **Projectile Spawning with Directional Logic:** The `SpawnLightningAttack` routine demonstrates how to spawn a projectile (`$CD`) and initialize its properties, including its `SprSubtype` and `SprAction`, based on Thunder Ghost's position relative to Link.
*   **`SprTimerA`, `SprTimerB`, `SprTimerC` Usage:** These timers are used to control the frequency of lightning attacks and the duration of facing/movement states.
*   **`Sprite_MoveLong`:** Used in the `CastThunderLeft` and `CastThunderRight` states, suggesting a specific movement behavior during the attack animation.
