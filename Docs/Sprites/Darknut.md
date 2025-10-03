# Darknut Sprite Analysis

This document provides a detailed analysis of the `darknut.asm` sprite, outlining its properties, core routines, and behavioral patterns.

## 1. Sprite Properties

The following `!SPRID` constants define Darknut's fundamental characteristics:

```asm
!SPRID              = Sprite_Darknut
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 12  ; Number of Health the sprite have (dynamically set in _Prep)
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 12  ; 00 to 31, can be viewed in sprite draw tool
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
**Note:** `!Health` is initially set to `12` but is dynamically determined during initialization based on Link's sword level. `!Damage` is `00`, implying damage is handled through other means (e.g., contact with Link's sword).

## 2. Core Routines

### 2.1. `Sprite_Darknut_Long` (Main Loop)

This is the primary entry point for Darknut's per-frame execution, called by the game engine. It handles drawing, shadow rendering, and then dispatches to the main logic routine if the sprite is active.

```asm
Sprite_Darknut_Long:
{
  PHB : PHK : PLB             ; Set up bank registers
  JSR Sprite_Darknut_Draw       ; Call drawing routine
  JSL Sprite_DrawShadow       ; Draw a shadow (if !Shadow is 01)
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive ; Check if sprite is active
    JSR Sprite_Darknut_Main     ; If active, run main logic
  .SpriteIsNotActive
  PLB                         ; Restore bank register
  RTL                         ; Return from long routine
}
```

### 2.2. `Sprite_Darknut_Prep` (Initialization)

This routine is executed once when Darknut is first spawned. It dynamically sets Darknut's health based on Link's current sword level, initializes `SprDefl` (deflection timer), and `SprTileDie` (tile for death animation).

```asm
Sprite_Darknut_Prep:
{
  PHB : PHK : PLB
  LDA.l $7EF359 : TAY           ; Get Link's sword level (0-3), adjust to 0-indexed
  LDA.w .health, Y : STA.w SprHealth, X ; Set health based on sword level
  LDA.b #$80 : STA.w SprDefl, X ; Initialize deflection timer
  LDA.b #%01100000 : STA.w SprTileDie, X ; Set tile for death animation
  PLB
  RTL

  .health                     ; Health values for each sword level
    db $04, $06, $08, $0A     ; 4, 6, 8, 10 HP
}
```

### 2.3. `Sprite_Darknut_Main` (Behavioral Logic)

This routine manages Darknut's AI, including probe spawning, parrying, movement, and animation. It uses `SprAction, X` to control its facing direction and animation.

```asm
Sprite_Darknut_Main:
{
  JSL GetDistance8bit_Long : CMP.b #$80 : BCS .no_probe ; Check distance to Link
    JSL Sprite_SpawnProbeAlways_long ; If close, spawn a probe
  .no_probe

  JSL Guard_ParrySwordAttacks       ; Handle parrying Link's sword attacks

  JSL Sprite_Move                   ; Apply velocity
  JSL Sprite_BounceFromTileCollision ; Handle collision with tiles
  JSL Sprite_DamageFlash_Long       ; Handle damage flashing

  JSL Sprite_CheckIfRecoiling       ; Check for recoil state

  JSL Sprite_CheckDamageFromPlayer : BCC .no_dano ; Check if Link damages Darknut
    LDA.b #$FF : STA.w SprTimerD, X ; If damaged, set timer D
  .no_dano

  LDA.w SprTimerA, X : BEQ +        ; Check timer A
    LDA.b #$90 : STA.w SprTimerD, X ; If timer A is not 0, set timer D
  +
  LDA.w SprTimerD, X : BEQ ++       ; Check timer D
    LDA.b #$08 : JSL Sprite_ApplySpeedTowardsPlayer ; Apply speed towards Link
    JSL Sprite_DirectionToFacePlayer ; Update facing direction
    TYA
    STA.w SprMiscC, X               ; Store facing direction in SprMiscC
    STA.w SprMiscE, X               ; Store facing direction in SprMiscE
    STA.w SprAction, X              ; Set SprAction to facing direction
    JSL Guard_ChaseLinkOnOneAxis    ; Chase Link along one axis
    JMP +++
  ++
  JSR Sprite_Darknut_BasicMove      ; If no timers, use basic movement
  +++

  JSR Goriya_HandleTileCollision    ; Handle tile collision (specific to Goriya, but used here)

  LDA.w SprAction, X
  JSL JumpTableLocal                ; Jump to animation routine based on SprAction

  dw FaceRight
  dw FaceLeft
  dw FaceDown
  dw FaceUp

  FaceUp:
  {
    %PlayAnimation(0,1,10)          ; Animate frames 0-1 every 10 frames
    RTS
  }

  FaceDown:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,10)          ; Animate frames 2-3 every 10 frames
    RTS
  }

  FaceLeft:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,5,10)          ; Animate frames 4-5 every 10 frames
    RTS
  }

  FaceRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(6,7,10)          ; Animate frames 6-7 every 10 frames
    RTS
  }
}
```

### 2.4. `Sprite_Darknut_BasicMove` (Basic Movement Logic)

This routine defines Darknut's basic movement patterns, which are executed when no special conditions (like being damaged or timers) are active. It uses `SprAction, X` to determine the current movement direction.

```asm
Sprite_Darknut_BasicMove:
{
  LDA.w SprAction, X
  JSL JumpTableLocal                ; Jump to movement routine based on SprAction

  dw MoveRight
  dw MoveLeft
  dw MoveDown
  dw MoveUp

  MoveUp:
  {
    LDA.b #-DarknutSpeed : STA.w SprYSpeed, X ; Set Y-speed to negative (move up)
    STZ.w SprXSpeed, X                ; Clear X-speed
    RTS
  }

  MoveDown:
  {
    LDA.b #DarknutSpeed : STA.w SprYSpeed, X  ; Set Y-speed to positive (move down)
    STZ.w SprXSpeed, X                ; Clear X-speed
    RTS
  }

  MoveLeft:
  {
    LDA.b #-DarknutSpeed : STA.w SprXSpeed, X ; Set X-speed to negative (move left)
    STZ.w SprYSpeed, X                ; Clear Y-speed
    RTS
  }

  MoveRight:
  {
    LDA.b #DarknutSpeed : STA.w SprXSpeed, X ; Set X-speed to positive (move right)
    STZ.w SprYSpeed, X                ; Clear Y-speed
    RTS
  }
}
```

### 2.5. `Sprite_Darknut_Draw` (Drawing Routine)

This routine is responsible for rendering Darknut's graphics. It uses a custom OAM (Object Attribute Memory) allocation and manipulation logic, similar to Booki, to handle its multi-tile appearance and animation. It dynamically determines the animation frame and applies offsets for each tile.

```asm
Sprite_Darknut_Draw:
{
  JSL Sprite_PrepOamCoord             ; Prepare OAM coordinates
  JSL Sprite_OAM_AllocateDeferToPlayer ; Allocate OAM slots, deferring to player

  LDA.w SprGfx, X : CLC : ADC $0D90, X : TAY ; Calculate animation frame index
  LDA .start_index, Y : STA $06       ; Store start index for tiles
  LDA.w SprFlash, X : STA $08         ; Store flash status

  PHX
  LDX .nbr_of_tiles, Y                ; Load number of tiles for current frame (minus 1)
  LDY.b #$00                          ; Initialize Y for OAM buffer offset
  .nextTile

  PHX                                 ; Save current Tile Index

  TXA : CLC : ADC $06                 ; Add Animation Index Offset

  PHA                                 ; Keep the value with animation index offset

  ASL A : TAX                         ; Multiply by 2 for word access

  REP #$20                            ; Set A to 16-bit mode

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y ; Store Y-coordinate with X-offset
  AND.w #$0100 : STA $0E              ; Check if Y-coord is off-screen (high bit)
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y ; Store X-coordinate with Y-offset
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20                            ; Set A to 8-bit mode
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y           ; If off-screen, move sprite off-screen
  STA $0E
  .on_screen_y

  PLX                                 ; Restore Tile Index
  INY
  LDA .chr, X : STA ($90), Y          ; Store character (tile) number
  INY
  LDA .properties, X : ORA $08 : STA ($90), Y ; Apply flash and store OAM properties

  PHY

  TYA : LSR #2 : TAY                  ; Calculate OAM buffer index for size

  LDA.w .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile           ; Loop for next tile

  PLX                                 ; Restore X (sprite index)

  RTS

  ; =========================================================
  ; OAM Data Tables
  .start_index
  db $00, $03, $06, $09, $0C, $0E, $10, $12
  .nbr_of_tiles
  db 2, 2, 2, 2, 1, 1, 1, 1
  .x_offsets
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, -12
  dw 0, -12
  dw 0, 12
  dw 0, 12
  .y_offsets
  dw -4, 0, -12
  dw -4, 0, -12
  dw 0, 12, 20
  dw 0, 12, 20
  dw 0, 8
  dw 0, 8
  dw 0, 8
  dw 0, 8
  .chr
  db $EF, $E6, $FF
  db $EF, $E6, $FF
  db $E2, $EF, $FF
  db $E2, $EF, $FF
  db $E0, $E8
  db $E4, $E8
  db $E0, $E8
  db $E4, $E8
  .properties
  db $B9, $39, $B9
  db $B9, $79, $B9
  db $39, $39, $39
  db $79, $39, $39
  db $39, $79
  db $39, $79
  db $79, $39
  db $79, $39
  .sizes
  db $00, $02, $00
  db $00, $02, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
}
```

## 3. Key Behaviors and Implementation Details

*   **Dynamic Health:** Darknut's health is determined at spawn time based on Link's current sword level, similar to Booki, allowing for dynamic difficulty scaling.
*   **Probe Spawning:** Darknut has the ability to spawn a probe (`Sprite_SpawnProbeAlways_long`) when Link is within a certain distance, adding a ranged attack or detection mechanism.
*   **Parrying Mechanics:** The `Guard_ParrySwordAttacks` routine suggests Darknut can actively defend against Link's sword attacks, potentially deflecting them or becoming temporarily invulnerable.
*   **Chasing on One Axis:** When damaged or under certain timer conditions, Darknut uses `Guard_ChaseLinkOnOneAxis` to pursue Link along either the horizontal or vertical axis, making its movement more predictable but still challenging.
*   **Basic Movement:** Darknut has a set of basic directional movements (`MoveUp`, `MoveDown`, `MoveLeft`, `MoveRight`) that it cycles through when not actively chasing or reacting to damage.
*   **Custom OAM Drawing:** Darknut utilizes a custom OAM drawing routine, similar to Booki, to handle its multi-tile sprite. This routine precisely positions and animates multiple 8x8 tiles to form the larger Darknut sprite. The use of `REP #$20` and `SEP #$20` for 16-bit coordinate calculations is also present here.
*   **`SprDefl` and `SprTileDie`:** `SprDefl` is used as a deflection timer, likely related to the parrying mechanic. `SprTileDie` specifies a custom tile to be used during its death animation.
*   **`SprMiscC` and `SprMiscE`:** These variables are used to store Darknut's facing direction, which influences both its movement and animation. `SprMiscC` is likely used for animation frame selection, while `SprMiscE` might be used for other directional logic.
*   **`Goriya_HandleTileCollision`:** The use of a collision handler named `Goriya_HandleTileCollision` suggests code reuse from another sprite, indicating a shared collision logic for certain enemy types.
