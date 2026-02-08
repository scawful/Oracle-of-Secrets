# Booki Sprite Analysis

This document provides a detailed analysis of the `booki.asm` sprite, outlining its properties, core routines, and behavioral patterns.

## 1. Sprite Properties

The following `!SPRID` constants define Booki's fundamental characteristics:

```asm
!SPRID              = Sprite_Booki
!NbrTiles           = 02  ; Number of tiles used in a frame
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

### 2.1. `Sprite_Booki_Long` (Main Loop)

This is the primary entry point for Booki's per-frame execution, called by the game engine. It handles drawing, shadow rendering, and then dispatches to the main logic routine if the sprite is active.

```asm
Sprite_Booki_Long:
{
  PHB : PHK : PLB             ; Set up bank registers
  JSR Sprite_Booki_Draw       ; Call drawing routine
  JSL Sprite_DrawShadow       ; Draw a shadow (if !Shadow is 01)
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive ; Check if sprite is active
    JSR Sprite_Booki_Main     ; If active, run main logic
  .SpriteIsNotActive
  PLB                         ; Restore bank register
  RTL                         ; Return from long routine
}
```

### 2.2. `Sprite_Booki_Prep` (Initialization)

This routine is executed once when Booki is first spawned. It dynamically sets Booki's health based on Link's current sword level and initializes `SprMiscB`.

```asm
Sprite_Booki_Prep:
{
  PHB : PHK : PLB
  LDA.l Sword : DEC A : TAY   ; Get Link's sword level (0-3), adjust to 0-indexed
  LDA.w .health, Y : STA.w SprHealth, X ; Set health based on sword level
  STZ.w SprMiscB, X           ; Initialize SprMiscB to 0
  PLB
  RTL

  .health                     ; Health values for each sword level
    db $04, $08, $10, $18     ; 4, 8, 16, 24 HP
}
```

### 2.3. `Sprite_Booki_Main` (Behavioral State Machine)

This routine manages Booki's AI through a state machine, using `SprAction, X` to determine the current behavior. It utilizes `JumpTableLocal` for efficient state transitions.

```asm
Sprite_Booki_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal          ; Jump to the routine specified by SprAction

  dw StalkPlayer              ; State 0
  dw HideFromPlayer           ; State 1
  dw HiddenFromPlayer         ; State 2
  dw ApproachPlayer           ; State 3

  StalkPlayer:
  {
    %PlayAnimation(0,1,16)    ; Animate frames 0-1 every 16 frames
    JSR Sprite_Booki_Move     ; Handle movement
    RTS
  }

  HideFromPlayer:
  {
    %PlayAnimation(0,4,16)    ; Animate frames 0-4 every 16 frames
    LDA.w SprTimerA, X : BNE + ; Check timer
      INC.w SprAction, X      ; If timer is 0, transition to HiddenFromPlayer
    +
    RTS
  }

  HiddenFromPlayer:
  {
    %PlayAnimation(4,4,16)    ; Animate frame 4 every 16 frames (static)
    JSR Sprite_Booki_Move     ; Handle movement
    JSL GetRandomInt : AND.b #$03 : BEQ + ; Random chance to transition
      INC.w SprAction, X      ; If random condition met, transition to ApproachPlayer
    +
    RTS
  }

  ApproachPlayer:
  {
    %PlayAnimation(5,9,16)    ; Animate frames 5-9 every 16 frames
    JSR Sprite_Booki_Move     ; Handle movement
    RTS
  }
}
```

### 2.4. `Sprite_Booki_Move` (Movement and Interaction Logic)

This routine is called by the various states in `Sprite_Booki_Main` to handle Booki's physical interactions and movement. It also manages Booki's "float" behavior (`SlowFloat` or `FloatAway`) based on `SprMiscB`.

```asm
Sprite_Booki_Move:
{
  JSL Sprite_Move                     ; Apply velocity
  JSL Sprite_BounceFromTileCollision  ; Handle collision with tiles
  JSL Sprite_PlayerCantPassThrough    ; Prevent player from passing through Booki
  JSL Sprite_DamageFlash_Long         ; Handle damage flashing
  JSL Sprite_CheckIfRecoiling         ; Check for recoil state

  JSL Sprite_IsToRightOfPlayer : CPY.b #$01 : BNE .ToRight ; Determine if Booki is to the right of Link
    LDA.b #$01 : STA.w SprMiscC, X     ; Set SprMiscC to 1 (for horizontal flip)
    JMP .Continue
  .ToRight
  STZ.w SprMiscC, X                   ; Set SprMiscC to 0 (no flip)
  .Continue

  JSL Sprite_CheckDamageToPlayer      ; Check if Booki damages Link
  JSL Sprite_CheckDamageFromPlayer : BCC .no_damage ; Check if Link damages Booki
    LDA.b #$01 : STA.w SprMiscB, X     ; If damaged, set SprMiscB to 1 (FloatAway state)
  .no_damage

  LDA.w SprMiscB, X
  JSL JumpTableLocal                  ; Jump to movement routine based on SprMiscB

  dw SlowFloat                        ; SprMiscB = 0
  dw FloatAway                        ; SprMiscB = 1

  SlowFloat:
  {
    LDY #$04
    JSL GetRandomInt : AND.b #$04     ; Introduce some randomness to movement
    JSL Sprite_FloatTowardPlayer      ; Float towards Link

    PHX
    JSL Sprite_DirectionToFacePlayer  ; Update facing direction
    ; Check if too close to player
    LDA.b $0E : CMP.b #$1A : BCS .NotTooClose
    LDA.b $0F : CMP.b #$1A : BCS .NotTooClose
      LDA.b #$01 : STA.w SprMiscB, X   ; If too close, switch to FloatAway
      LDA.b #$20 : STA.w SprTimerA, X  ; Set timer
      %GotoAction(1)                  ; Transition to HideFromPlayer state
    .NotTooClose
    PLX

    RTS
  }

  FloatAway:
  {
    JSL GetRandomInt : AND.b #$04     ; Introduce some randomness to movement
    JSL Sprite_FloatAwayFromPlayer    ; Float away from Link

    PHX
    JSL Sprite_DirectionToFacePlayer  ; Update facing direction
    ; Check if far enough from player
    LDA.b $0E : CMP.b #$1B : BCC .NotTooClose
    LDA.b #$1B : CMP.b $0F : BCC .NotTooClose ; Corrected comparison for $0F
      LDA.b #$00 : STA.w SprMiscB, X   ; If far enough, switch to SlowFloat
      %GotoAction(0)                  ; Transition to StalkPlayer state
    .NotTooClose
    PLX

    RTS
  }
}
```

### 2.5. `Sprite_Booki_Draw` (Drawing Routine)

This routine is responsible for rendering Booki's graphics. It uses a custom OAM (Object Attribute Memory) allocation and manipulation logic rather than the `%DrawSprite()` macro. It dynamically determines the animation frame and applies horizontal flipping based on `SprMiscC`.

```asm
Sprite_Booki_Draw:
{
  JSL Sprite_PrepOamCoord             ; Prepare OAM coordinates
  JSL Sprite_OAM_AllocateDeferToPlayer ; Allocate OAM slots, deferring to player

  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : TAY ; Calculate animation frame index
  LDA .start_index, Y : STA $06       ; Store start index for tiles

  LDA.w SprFlash, X : STA $08         ; Store flash status
  LDA.w SprMiscC, X : STA $09         ; Store horizontal flip status (0 or 1)

  PHX
  LDX .nbr_of_tiles, Y                ; Load number of tiles for current frame (minus 1)
  LDY.b #$00                          ; Initialize Y for OAM buffer offset
  .nextTile

  PHX                                 ; Save current Tile Index
  TXA : CLC : ADC $06                 ; Add Animation Index Offset
  PHA                                 ; Keep the value with animation index offset

  ASL A : TAX                         ; Multiply by 2 for word access

  REP #$20                            ; Set A to 16-bit mode

  LDA $00 : STA ($90), Y              ; Store Y-coordinate
  AND.w #$0100 : STA $0E              ; Check if Y-coord is off-screen (high bit)
  INY
  LDA $02 : STA ($90), Y              ; Store X-coordinate
  CLC : ADC #$0010 : CMP.w #$0100     ; Check if X-coord is off-screen
  SEP #$20                            ; Set A to 8-bit mode
  BCC .on_screen_y                    ; If on screen, continue

  LDA.b #$F0 : STA ($90), Y           ; If off-screen, move sprite off-screen
  STA $0E
  .on_screen_y

  PLX                                 ; Restore Tile Index
  INY
  LDA .chr, X : STA ($90), Y          ; Store character (tile) number
  INY

  LDA.b $09 : BEQ .ToRight            ; Check SprMiscC for horizontal flip
  LDA.b #$29 : JMP .Prop              ; If 1, use properties for flipped
  .ToRight
  LDA.b #$69                          ; If 0, use properties for normal
  .Prop
  ORA $08 : STA ($90), Y              ; Apply flash and store OAM properties

  PHY

  TYA : LSR #2 : TAY                  ; Calculate OAM buffer index for size
  LDA.b #$02 : ORA $0F : STA ($92), Y ; Store size (16x16) in OAM buffer

  PLY : INY

  PLX : DEX : BPL .nextTile           ; Loop for next tile

  PLX                                 ; Restore X (sprite index)

  RTS

  ; =========================================================
  ; OAM Data Tables
  .start_index
  db $00, $01, $02, $03, $04, $05, $06, $07, $08, $09
  .nbr_of_tiles
  db 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ; All frames use 1 tile (0-indexed)
  .chr
  db $0E, $0C, $0A, $2C, $2E, $2E, $0A, $2C, $0C, $0E ; Tile numbers for each frame
}
```

## 3. Key Behaviors and Implementation Details

*   **Dynamic Health:** Booki's health is not a fixed property but is determined at spawn time based on Link's current sword level. This allows for dynamic difficulty scaling.
*   **State Management:** Booki employs a robust state machine using `SprAction, X` and `JumpTableLocal` to manage its behaviors: `StalkPlayer`, `HideFromPlayer`, `HiddenFromPlayer`, and `ApproachPlayer`. Transitions between these states are triggered by timers, random chance, or player proximity.
*   **Player Interaction:**
    *   **Stalking/Approaching:** Booki uses `Sprite_FloatTowardPlayer` to move towards Link.
    *   **Hiding/Floating Away:** Booki uses `Sprite_FloatAwayFromPlayer` to retreat from Link, often triggered by taking damage or getting too close.
    *   **Damage:** Booki can damage Link on contact (`Sprite_CheckDamageToPlayer`) and reacts to damage from Link by transitioning to a `FloatAway` state.
*   **Directional Facing:** `SprMiscC, X` is used as a flag to control horizontal flipping in the drawing routine, ensuring Booki always faces Link.
*   **Custom OAM Drawing:** Unlike many sprites that might use the `%DrawSprite()` macro, Booki implements its OAM drawing logic directly. This provides fine-grained control over its appearance, including dynamic tile selection and horizontal flipping. The `REP #$20` and `SEP #$20` instructions are used to temporarily switch the accumulator to 16-bit mode for coordinate calculations, demonstrating careful management of the Processor Status Register.
*   **Randomness:** `GetRandomInt` is used to introduce variability in Booki's movement patterns and state transitions, making its behavior less predictable.
*   **`SprMiscB` Usage:** This variable acts as a sub-state for movement, toggling between `SlowFloat` (approaching) and `FloatAway` (retreating) behaviors.
*   **`SprTimerA` Usage:** Used in the `HideFromPlayer` state to control how long Booki remains in that state before transitioning.
*   **`Sprite_PlayerCantPassThrough`:** Ensures Booki acts as a solid object that Link cannot simply walk through.
