# Goriya Sprite Analysis

This document provides a detailed analysis of the `goriya.asm` sprite, outlining its properties, core routines, and behavioral patterns.

## 1. Sprite Properties

The following `!SPRID` constants define Goriya's fundamental characteristics:

```asm
!SPRID              = Sprite_Goriya
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have (dynamically set in _Prep)
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
**Note:** `!Health` and `!Damage` are initially set to `00` but are dynamically determined during initialization.

## 2. Core Routines

### 2.1. `Sprite_Goriya_Long` (Main Loop)

This is the primary entry point for Goriya's per-frame execution, called by the game engine. It handles drawing, shadow rendering, and then dispatches to the main logic routine if the sprite is active. Notably, it checks `SprSubtype, X` to determine if it's the main Goriya sprite or a boomerang, and calls the appropriate drawing routine.

```asm
Sprite_Goriya_Long:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : BEQ +       ; Check SprSubtype
    JSR Sprite_Boomerang_Draw       ; If SprSubtype is not 0, draw as boomerang
    JMP ++
  +
  JSR Sprite_Goriya_Draw            ; If SprSubtype is 0, draw as Goriya
  JSL Sprite_DrawShadow
  ++
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive ; Check if sprite is active
    JSR Sprite_Goriya_Main          ; If active, run main logic
  .SpriteIsNotActive
  PLB
  RTL
}
```

### 2.2. `Sprite_Goriya_Prep` (Initialization)

This routine is executed once when Goriya is first spawned. It sets Goriya's health to `08` (one heart).

```asm
Sprite_Goriya_Prep:
{
  PHB : PHK : PLB
  LDA.b #$08 : STA.w SprHealth, X    ; Set health to 8
  PLB
  RTL
}
```

### 2.3. `Sprite_Goriya_Main` (Behavioral State Machine)

This routine manages Goriya's AI through a state machine, using `SprAction, X` to determine the current behavior. It utilizes `JumpTableLocal` for efficient state transitions, including walking in different directions and a boomerang attack state.

```asm
Sprite_Goriya_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal                ; Jump to the routine specified by SprAction

  dw Goriya_WalkingUp
  dw Goriya_WalkingDown
  dw Goriya_WalkingLeft
  dw Goriya_WalkingRight
  dw BoomerangAttack

  Goriya_WalkingUp:
  {
    %PlayAnimation(0, 1, 10)        ; Animate frames 0-1 every 10 frames
    JSR Sprite_Goriya_Move          ; Handle movement
    RTS
  }

  Goriya_WalkingDown:
  {
    %PlayAnimation(2, 3, 10)        ; Animate frames 2-3 every 10 frames
    JSR Sprite_Goriya_Move          ; Handle movement
    RTS
  }

  Goriya_WalkingLeft:
  {
    %StartOnFrame(4)
    %PlayAnimation(4, 5, 10)        ; Animate frames 4-5 every 10 frames
    JSR Sprite_Goriya_Move          ; Handle movement
    RTS
  }

  Goriya_WalkingRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(6, 7, 10)        ; Animate frames 6-7 every 10 frames
    JSR Sprite_Goriya_Move          ; Handle movement
    RTS
  }

  BoomerangAttack:
  {
    %PlayAnimation(0, 3, 6)         ; Animate frames 0-3 every 6 frames

    LDA.w SprTimerD, X : BNE +      ; Check timer D
      LDA.b #$16
      JSL Sprite_ApplySpeedTowardsPlayer ; Apply speed towards Link
      %SetTimerD($50)               ; Set timer D
    +

    JSL Sprite_Move                 ; Apply velocity
    JSL Sprite_SpawnSparkleGarnish  ; Spawn sparkle effect

    JSL Sprite_CheckDamageToPlayer : BCC .no_dano ; Check if Goriya damages Link
      LDA.b #$FF : STA.w SprTimerD, X ; If damaged, set timer D
      JSL Sprite_InvertSpeed_XY     ; Invert speed
    .no_dano

    JSL Sprite_CheckDamageFromPlayer : BCC + ; Check if Link damages Goriya
      JSL Sprite_InvertSpeed_XY     ; If damaged, invert speed
    +

    JSL Sprite_CheckTileCollision   ; Check for tile collision
    LDA.w SprCollision, X : BEQ +   ; If no collision
      STZ.w SprState, X             ; Clear sprite state (despawn?)
    +

    RTS
  }
}
```

### 2.4. `Sprite_Goriya_Move` (Movement and Interaction Logic)

This routine is called by the various walking states in `Sprite_Goriya_Main` to handle Goriya's physical interactions and movement. It also manages the logic for throwing a boomerang and changing movement directions.

```asm
Sprite_Goriya_Move:
{
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_PlayerCantPassThrough

  JSL Sprite_DamageFlash_Long

  JSL Sprite_CheckDamageToPlayer
  JSL Sprite_CheckDamageFromPlayer

  JSL Sprite_CheckIfRecoiling

  JSR Goriya_HandleTileCollision    ; Handle tile collision and change direction

  LDA.w SprTimerD, X : BNE ++
    JSL GetRandomInt : AND.b #$9F : BNE ++
      LDA.b #$04 : STA.w SprMiscB, X ; Set SprMiscB for boomerang attack
      %SetTimerD($FF)
      JSR Goriya_BoomerangAttack    ; Spawn boomerang
      JMP +
  ++

  LDA.w SprTimerC, X : BNE +
    JSL GetRandomInt : AND.b #$03
    STA.w SprMiscB, X               ; Set SprMiscB for new movement direction
    %SetTimerC(60)
  +

  LDA.w SprMiscB, X
  JSL JumpTableLocal                ; Jump to movement routine based on SprMiscB

  dw Goriya_MoveUp
  dw Goriya_MoveDown
  dw Goriya_MoveLeft
  dw Goriya_MoveRight
  dw Goriya_Wait

  Goriya_MoveUp:
  {
    LDA.b #-GoriyaMovementSpeed : STA.w SprYSpeed, X
    STZ.w SprXSpeed, X
    %GotoAction(0)                  ; Transition to Goriya_WalkingUp
    LDA.b #$00 : STA.w SprMiscE, X
    RTS
  }

  Goriya_MoveDown:
  {
    LDA.b #GoriyaMovementSpeed : STA.w SprYSpeed, X
    STZ.w SprXSpeed, X
    %GotoAction(1)                  ; Transition to Goriya_WalkingDown
    LDA.b #$01 : STA.w SprMiscE, X
    RTS
  }

  Goriya_MoveLeft:
  {
    STZ.w SprYSpeed, X
    LDA.b #-GoriyaMovementSpeed : STA.w SprXSpeed, X
    %GotoAction(2)                  ; Transition to Goriya_WalkingLeft
    LDA.b #$02 : STA.w SprMiscE, X
    RTS
  }

  Goriya_MoveRight:
  {
    STZ.w SprYSpeed, X
    LDA.b #GoriyaMovementSpeed : STA.w SprXSpeed, X
    %GotoAction(3)                  ; Transition to Goriya_WalkingRight
    LDA.b #$03 : STA.w SprMiscE, X
    RTS
  }

  Goriya_Wait:
  {
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    %GotoAction(0)                  ; Transition to Goriya_WalkingUp (default)
    RTS
  }
}
```

### 2.5. `Goriya_HandleTileCollision`

This routine is called to handle Goriya's collision with tiles. Upon collision, it randomly selects a new movement direction and sets a timer (`SprTimerC`).

```asm
Goriya_HandleTileCollision:
{
  JSL Sprite_CheckTileCollision
  LDA.w SprCollision, X : BEQ ++
    JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X ; Randomly choose new direction
  +
  STA.w SprMiscE, X
  %SetTimerC(60)                    ; Set timer C for 60 frames
  ++
  RTS
}
```

### 2.6. `Goriya_BoomerangAttack`

This routine is responsible for spawning the boomerang sprite. It sets up the boomerang's initial properties, including its `SprSubtype` (to differentiate it from the main Goriya), action, position, and health.

```asm
Goriya_BoomerangAttack:
{
  LDA.b #$2C                          ; Sprite ID for boomerang (assuming $2C is the boomerang sprite ID)
  JSL Sprite_SpawnDynamically : BMI + ; Spawn a new sprite dynamically
    LDA.b #$01 : STA.w SprSubtype, Y ; Set SprSubtype to 1 for the boomerang
    LDA.b #$04 : STA.w SprAction, Y  ; Set action for boomerang (e.g., flying)
    LDA.w SprX, X : STA.w SprX, Y   ; Copy Goriya's X position to boomerang
    LDA.w SprY, X : STA.w SprY, Y   ; Copy Goriya's Y position to boomerang
    LDA.w SprXH, X : STA.w SprXH, Y
    LDA.w SprYH, X : STA.w SprYH, Y
    LDA.b #$01 : STA.w SprNbrOAM, Y  ; Set number of OAM entries
    LDA.b #$40 : STA.w SprHealth, Y  ; Set boomerang health
    LDA.b #$00 : STA.w SprHitbox, Y  ; Set boomerang hitbox
  +
  RTS
}
```

### 2.7. `Sprite_Goriya_Draw` (Goriya Drawing Routine)

This routine is responsible for rendering Goriya's graphics. It uses a custom OAM allocation and manipulation logic to handle its multi-tile appearance and animation. It dynamically determines the animation frame and applies offsets for each tile.

```asm
Sprite_Goriya_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : TAY ; Calculate animation frame index
  LDA.w .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08

  PHX
    LDX .nbr_of_tiles, Y ;amount of tiles - 1
    LDY.b #$00
    .nextTile
    ; -------------------------------------------------------
    PHX ; Save current Tile Index?
      TXA : CLC : ADC $06 ; Add Animation Index Offset
      PHA ; Keep the value with animation index offset?

      ASL A : TAX

      REP #$20
        LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
        AND.w #$0100 : STA $0E : INY
        LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
        CLC : ADC #$0010 : CMP.w #$0100
      SEP #$20
      BCC .on_screen_y

      ; Put the sprite out of the way
      LDA.b #$F0 : STA ($90), Y : STA $0E
      .on_screen_y

    PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
    INY
    LDA .chr, X : STA ($90), Y : INY
    LDA .properties, X : ORA $08 : STA ($90), Y

    PHY
      TYA : LSR #2 : TAY
      LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
    PLY : INY
    PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $02, $04, $06, $08, $0A, $0C, $0E
  .nbr_of_tiles
  db 1, 1, 1, 1, 1, 1, 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw 0, -9
  dw 0, -9
  dw 0, -10
  dw 0, -10
  dw 0, -10
  dw 0, -9
  dw 0, -9
  dw -1, -10
  .chr
  ; Body  Head
  db $E4, $C0
  db $E4, $C0
  db $E6, $C2
  db $E6, $C2
  db $E2, $C4
  db $E0, $C4
  db $E2, $C4
  db $E0, $C4
  .properties
  db $2D, $2D
  db $6D, $2D
  db $2D, $2D
  db $6D, $2D
  db $2D, $2D
  db $2D, $2D
  db $6D, $6D
  db $6D, $6D
}
```

### 2.8. `Sprite_Boomerang_Draw` (Boomerang Drawing Routine)

This routine is responsible for rendering the boomerang's graphics. It also uses a custom OAM allocation and manipulation logic.

```asm
Sprite_Boomerang_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08


  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  .start_index
  db $00, $01, $02, $03
  .nbr_of_tiles
  db 0, 0, 0, 0
  .chr
  db $26
  db $26
  db $26
  db $26
  .properties
  db $22
  db $A2
  db $E2
  db $62
}
```

## 3. Key Behaviors and Implementation Details

*   **Dual Role (Goriya and Boomerang):** The `Sprite_Goriya_Long` routine uses `SprSubtype, X` to determine if the current sprite instance is the main Goriya or a boomerang it has thrown. This allows a single sprite ID to manage two distinct entities.
*   **Boomerang Attack:** Goriya actively throws a boomerang (`Goriya_BoomerangAttack`) at Link, which then becomes an independent sprite with its own drawing and movement logic (`BoomerangAttack` state in `Sprite_Goriya_Main` and `Sprite_Boomerang_Draw`).
*   **Dynamic Health:** Goriya's health is set to a fixed value of `08` (one heart) during initialization.
*   **State Management:** Goriya uses `SprAction, X` and `JumpTableLocal` to manage its walking states (`Goriya_WalkingUp`, `Goriya_WalkingDown`, `Goriya_WalkingLeft`, `Goriya_WalkingRight`) and its `BoomerangAttack` state.
*   **Movement Patterns:** Goriya moves in random directions, with `Goriya_HandleTileCollision` triggering a new random direction upon hitting a tile. It also has a `Goriya_Wait` state.
*   **Custom OAM Drawing:** Both the Goriya and its boomerang utilize custom OAM drawing routines (`Sprite_Goriya_Draw` and `Sprite_Boomerang_Draw`) for precise control over their multi-tile graphics and animation. The use of `REP`/`SEP` for 16-bit coordinate calculations is present in both.
*   **Code Reuse:** The `Goriya_HandleTileCollision` routine is notably reused by the Darknut sprite, indicating a shared and modular approach to tile collision handling for certain enemy types.
*   **`SprMiscB` Usage:** This variable is used to store the current movement direction (0-4) for Goriya's random movement.
*   **`SprMiscE` Usage:** This variable also stores the current movement direction, likely for animation or other directional logic.
*   **`SprTimerC` and `SprTimerD` Usage:** These timers are used to control the duration of movement states and the frequency of boomerang attacks.
