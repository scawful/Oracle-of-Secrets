# Puffstool Sprite Analysis

This document provides a detailed analysis of the `puffstool.asm` sprite, outlining its properties, core routines, and behavioral patterns.

## 1. Sprite Properties

The following `!SPRID` constants define Puffstool's fundamental characteristics:

```asm
!SPRID              = Sprite_Puffstool
!NbrTiles           = 02  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 0   ; Number of Health the sprite have (dynamically set in _Prep)
!Damage             = 0   ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 0   ; Unused in this template (can be 0 to 7)
!Hitbox             = 0   ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 0   ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss
```
**Note:** `!Health`, `!Damage`, `!Hitbox`, and `!Prize` are initially set to `0` but are dynamically determined during initialization.

## 2. Core Routines

### 2.1. `Sprite_Puffstool_Long` (Main Loop)

This is the primary entry point for Puffstool's per-frame execution. It handles drawing, shadow rendering, and then dispatches to the main logic routine if the sprite is active.

```asm
Sprite_Puffstool_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Puffstool_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Puffstool_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

### 2.2. `Sprite_Puffstool_Prep` (Initialization)

This routine is executed once when Puffstool is first spawned. It sets its health based on Link's sword level and initializes `SprDefl`.

```asm
Sprite_Puffstool_Prep:
{
  PHB : PHK : PLB
  LDA.l $7EF359 : TAY
  LDA.w .health, Y : STA.w SprHealth, X ; Set health based on sword level
  LDA.b #$80 : STA.w SprDefl, X
  PLB
  RTL

  .health
    db $04, $08, $0A, $10 ; Health values for each sword level
}
```

### 2.3. `Sprite_Puffstool_Main` (Behavioral State Machine)

This routine manages Puffstool's AI through a state machine, using `SprAction, X` to determine its current behavior. It includes states for walking, being stunned, and spawning spores.

```asm
Sprite_Puffstool_Main:
{
  %SpriteJumpTable(Puffstool_Walking,
                   Puffstool_Stunned,
                   Puffstool_Spores)

  Puffstool_Walking:
  {
    %PlayAnimation(0,6,10)

    JSL Sprite_PlayerCantPassThrough

    LDA.w SprTimerA, X : BNE + ; If timer A is not 0
      JSL Sprite_SelectNewDirection ; Select a new direction
    +
    JSL Sprite_MoveXyz
    JSL Sprite_BounceFromTileCollision
    JSL Sprite_DamageFlash_Long
    JSL ThrownSprite_TileAndSpriteInteraction_long ; Interact with thrown objects
    JSL Sprite_CheckIfRecoiling
    JSL Sprite_CheckDamageFromPlayer : BCC .no_dano ; Check if Link damages Puffstool
      %GotoAction(1) ; Transition to Puffstool_Stunned
      %SetTimerA($60)
      %SetTimerF($20)
    .no_dano

    RTS
  }

  Puffstool_Stunned:
  {
    %PlayAnimation(7,7,10)

    JSL Sprite_CheckIfLifted
    JSL Sprite_DamageFlash_Long
    JSL ThrownSprite_TileAndSpriteInteraction_long

    LDA.w SprTimerA, X : BNE + ; If timer A is not 0
      %GotoAction(0) ; Transition back to Puffstool_Walking

      JSL GetRandomInt : AND.b #$1F : BEQ .bomb ; Random chance to spawn bomb
        JSR Puffstool_SpawnSpores ; Spawn spores
        RTS
      .bomb
      LDA.b #$4A ; SPRITE 4A (Bomb sprite ID)
      LDY.b #$0B
      JSL Sprite_SpawnDynamically : BMI .no_space
        JSL Sprite_SetSpawnedCoordinates
        JSL Sprite_TransmuteToBomb ; Transform into a bomb
      .no_space
    +
    RTS
  }

  Puffstool_Spores:
  {
    %StartOnFrame(8)
    %PlayAnimation(8,11,10)

    JSL Sprite_MoveXyz
    JSL Sprite_CheckDamageToPlayerSameLayer

    LDA.w SprTimerC, X : BNE + ; If timer C is not 0
      JSL ForcePrizeDrop_long ; Force prize drop
      STZ.w SprState, X       ; Clear sprite state (despawn?)
    +
    RTS
  }
}
```

### 2.4. `Puffstool_SpawnSpores`

This routine is responsible for spawning spore projectiles. It plays a sound effect and then spawns multiple spore sprites, setting their initial properties like speed, altitude, and timers.

```asm
Puffstool_SpawnSpores:
{
  LDA.b #$0C ; SFX2.0C
  JSL $0DBB7C ; SpriteSFX_QueueSFX2WithPan

  LDA.b #$03 : STA.b $0D ; Number of spores to spawn

  .nth_child
  LDA.b #$B1 ; Spore sprite ID (assuming $B1 is the spore sprite ID)
  JSL Sprite_SpawnDynamically : BMI .no_space
    JSL Sprite_SetSpawnedCoordinates
    PHX

    LDX.b $0D
    LDA.w .speed_x, X : STA.w SprXSpeed, Y
    LDA.w .speed_y, X : STA.w SprYSpeed, Y
    LDA.b #$20 : STA.w $0F80, Y ; Altitude
    LDA.b #$FF : STA.w $0E80, Y ; Gravity
    LDA.b #$40 : STA.w SprTimerC, Y
    LDA.b #$01 : STA.w SprSubtype, Y
    LDA.b #$02 : STA.w SprAction, Y

    PLX
  .no_space
  DEC.b $0D
  BPL .nth_child
  RTS

  .speed_x
  db  11, -11, -11, 11

  .speed_y
  db   0,  11,   0, -11
}
```

### 2.5. `Sprite_Puffstool_Draw` (Drawing Routine)

This routine is responsible for rendering Puffstool's graphics. It uses the `%DrawSprite()` macro, which reads from a set of data tables to handle its multi-tile appearance and animation.

```asm
Sprite_Puffstool_Draw:
{
  %DrawSprite()

  .start_index
    db $00, $02, $04, $06, $08, $0A, $0C, $0E, $0F, $10, $11, $12
  .nbr_of_tiles
    db 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0
  .x_offsets
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 4
  .y_offsets
    dw -8, 0
    dw 0, -8
    dw 0, -8
    dw 0, -8
    dw 0, -8
    dw 0, -8
    dw 0, -8
    dw 0
    dw 0
    dw 0
    dw 0
    dw 4
  .chr
    db $C0, $D0
    db $D2, $C2
    db $D4, $C4
    db $D2, $C2
    db $D0, $C0
    db $D2, $C2
    db $D4, $C4
    db $D6
    db $EA
    db $C8
    db $E8
    db $F7
  .properties
    db $33, $33
    db $33, $33
    db $33, $33
    db $33, $33
    db $33, $33
    db $73, $73
    db $73, $73
    db $3D
    db $33
    db $33
    db $33
    db $33
  .sizes
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02
    db $02
    db $02
    db $02
    db $00
}
```

## 3. Key Behaviors and Implementation Details

*   **Dynamic Health:** Puffstool's health is determined at spawn time based on Link's current sword level, allowing for dynamic difficulty scaling.
*   **State Management:** Puffstool uses `SprAction, X` and `%SpriteJumpTable` to manage its `Puffstool_Walking`, `Puffstool_Stunned`, and `Puffstool_Spores` states.
*   **Movement Patterns:** In its walking state, Puffstool moves with random direction changes (`Sprite_SelectNewDirection`) and interacts with the environment (`Sprite_MoveXyz`, `Sprite_BounceFromTileCollision`).
*   **Stunned State and Counter-Attack:** When damaged, Puffstool enters a `Puffstool_Stunned` state. After a timer, it either spawns multiple spores (`Puffstool_SpawnSpores`) or, with a random chance, transforms into a bomb (`Sprite_TransmuteToBomb`). This provides a unique counter-attack mechanism.
*   **Spore Attack:** Puffstool can spawn multiple spore projectiles (`Puffstool_SpawnSpores`) that have their own movement and interaction logic. These spores are spawned with initial speed, altitude, and gravity.
*   **Bomb Spawning/Transformation:** A unique behavior where Puffstool can transform into a bomb (`Sprite_TransmuteToBomb`) when stunned, adding an element of surprise and danger.
*   **Interaction with Thrown Objects:** The use of `ThrownSprite_TileAndSpriteInteraction_long` suggests Puffstool can be lifted and thrown by Link, or interacts with other thrown objects.
*   **Custom OAM Drawing:** Puffstool uses the `%DrawSprite()` macro with detailed OAM data tables to render its multi-tile appearance and animations across its different states.
*   **`SprTimerA`, `SprTimerF`, `SprTimerC` Usage:** These timers control the duration of the stunned state, the delay before spawning spores/bombs, and the lifespan of the spawned spores.
