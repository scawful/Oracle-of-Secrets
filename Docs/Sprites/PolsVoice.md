# Pols Voice Sprite Analysis

This document provides a detailed analysis of the `pols_voice.asm` sprite, outlining its properties, core routines, and behavioral patterns.

## 1. Sprite Properties

The following `!SPRID` constants define Pols Voice's fundamental characteristics:

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
**Note:** `!Health` is set to `10` and is not dynamically determined by Link's sword level.

## 2. Core Routines

### 2.1. `Sprite_PolsVoice_Long` (Main Loop)

This is the primary entry point for Pols Voice's per-frame execution. It handles drawing, shadow rendering, and then dispatches to the main logic routine if the sprite is active.

```asm
Sprite_PolsVoice_Long:
{
  PHB : PHK : PLB
  JSR Sprite_PolsVoice_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_PolsVoice_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

### 2.2. `Sprite_PolsVoice_Prep` (Initialization)

This routine is executed once when Pols Voice is first spawned. It initializes `SprTimerA` to `$80` and clears `SprDefl` and `SprTileDie`.

```asm
Sprite_PolsVoice_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprTimerA, X
  STZ.w SprDefl, X
  STZ.w SprTileDie, X
  PLB
  RTL
}
```

### 2.3. `Sprite_PolsVoice_Main` (Behavioral State Machine)

This routine manages Pols Voice's AI through a state machine, using `SprAction, X` to determine its current behavior. It includes states for moving around and hopping around, with a unique interaction based on the flute song.

```asm
Sprite_PolsVoice_Main:
{
  JSR PolsVoice_CheckForFluteSong ; Check for flute song interaction

  %SpriteJumpTable(PolsVoice_MoveAround,
                   PolsVoice_HopAround)

  PolsVoice_MoveAround:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,3,10)

    ;$09 = speed, $08 = max height
    LDA #$05 : STA $09
    LDA #$02 : STA $08
    JSL Sprite_BounceTowardPlayer
    JSL Sprite_BounceFromTileCollision
    JSL Sprite_DamageFlash_Long

    %DoDamageToPlayerSameLayerOnContact()

    JSL GetRandomInt : AND #$3F : BNE .not_done ; Random chance to change state
      LDA #$04 : STA.w SprTimerA, X
      %GotoAction(1) ; Transition to PolsVoice_HopAround
    .not_done

    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage ; Check if Link damages Pols Voice
      JSL Sprite_DirectionToFacePlayer

      ; Apply the speed positive or negative speed
      LDA $0E : BPL .not_up
        LDA #$20 : STA.w SprYSpeed, X
        BRA .not_down
      .not_up
      LDA #$E0 : STA.w SprYSpeed, X
      .not_down
      LDA $0F : BPL .not_right
        LDA #$20 : STA.w SprXSpeed, X
        BRA .not_left
      .not_right
      LDA #$E0 : STA.w SprXSpeed, X
      .not_left
      LDA #$04 : STA.w SprTimerA, X
      %GotoAction(1) ; Transition to PolsVoice_HopAround
    .no_damage
    RTS
  }

  PolsVoice_HopAround:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,4,10)

    JSL Sprite_MoveXyz
    JSL Sprite_BounceFromTileCollision
    JSL Sprite_DamageFlash_Long

    %DoDamageToPlayerSameLayerOnContact()

    LDA.w SprTimerA, X : BNE .not_done ; If timer A is not 0
      %GotoAction(0) ; Transition back to PolsVoice_MoveAround
    .not_done
    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage ; Check if Link damages Pols Voice
      JSL Sprite_InvertSpeed_XY ; Invert speed
    .no_damage
    RTS
  }
}
```

### 2.4. `PolsVoice_CheckForFluteSong`

This routine checks if the player is currently playing the flute (`SongFlag`). If the flute is being played, Pols Voice despawns (`STZ.w SprState, X`) and forces a prize drop.

```asm
PolsVoice_CheckForFluteSong:
{
  ; If the player plays the flute
  LDA.b SongFlag : BEQ + ; Check SongFlag
    LDA.b #$03 : STA.w SprState, X ; Set sprite state to despawn
    JSL ForcePrizeDrop_long ; Force prize drop
  +
  RTS
}
```

### 2.5. `Sprite_PolsVoice_Draw` (Drawing Routine)

This routine is responsible for rendering Pols Voice's graphics. It uses the `%DrawSprite()` macro, which reads from a set of data tables to handle its appearance and animation.

```asm
Sprite_PolsVoice_Draw:
{
  %DrawSprite()

  .start_index
    db $00, $01, $02, $03, $04
  .nbr_of_tiles
    db 0, 0, 0, 0, 1
  .x_offsets
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0, 0
  .y_offsets
    dw 0
    dw 0
    dw 0
    dw 0
    dw -4, -20
  .chr
    db $6C
    db $6A
    db $6C
    db $6A
    db $6E, $4E
  .properties
    db $3B
    db $3B
    db $3B
    db $7B
    db $3B, $3B
  .sizes
    db $02
    db $02
    db $02
    db $02
    db $02, $02
}
```

## 3. Key Behaviors and Implementation Details

*   **Fixed Health:** Unlike many other sprites, Pols Voice has a fixed health of `10` and its health is not dynamically scaled based on Link's sword level.
*   **State Management:** Pols Voice uses `SprAction, X` and `%SpriteJumpTable` to manage its `PolsVoice_MoveAround` and `PolsVoice_HopAround` states. Transitions between these states are triggered by timers or random chance.
*   **Movement Patterns:** Pols Voice moves by bouncing towards the player (`Sprite_BounceTowardPlayer`) and also has a hopping movement (`PolsVoice_HopAround`). It reacts to tile collisions by bouncing (`Sprite_BounceFromTileCollision`).
*   **Flute Song Interaction:** A unique and defining characteristic of Pols Voice is its vulnerability to the flute song. When Link plays the flute (`SongFlag` is set), Pols Voice immediately despawns and drops a prize (`ForcePrizeDrop_long`). This is a classic Zelda enemy mechanic.
*   **Damage Reaction:** When damaged by Link, Pols Voice inverts its speed (`Sprite_InvertSpeed_XY`) and transitions to the `PolsVoice_HopAround` state, providing a temporary reprieve or change in behavior.
*   **Custom OAM Drawing:** Pols Voice uses the `%DrawSprite()` macro with OAM data tables to render its appearance and animations.
*   **`SprTimerA` Usage:** This timer controls the duration of the `PolsVoice_HopAround` state before transitioning back to `PolsVoice_MoveAround`.
