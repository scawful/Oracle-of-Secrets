# Eon Owl / Kaepora Gaebora

## Overview
This sprite is a sophisticated NPC implementation that serves as both the "Eon Owl" and "Kaepora Gaebora" (a character from The Legend of Zelda: Ocarina of Time). Its appearance, behavior, and interactions are highly conditional, depending on the player's location and various game progression flags.

## Sprite Properties
*   **`!SPRID`**: `Sprite_EonOwl` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `03`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `00`
*   **`!Persist`**: `00`
*   **`!Statis`**: `00`
*   **`!CollisionLayer`**: `00`
*   **`!CanFall`**: `00`
*   **`!DeflectArrow`**: `00`
*   **`!WaterSprite`**: `00`
*   **`!Blockable`**: `00`
*   **`!Prize`**: `00`
*   **`!Sound`**: `00`
*   **`!Interaction`**: `00`
*   **`!Statue`**: `00`
*   **`!DeflectProjectiles`**: `01` (Deflects all projectiles)
*   **`!ImperviousArrow`**: `01` (Impervious to arrows)
*   **`!ImpervSwordHammer`**: `01` (Impervious to sword and hammer attacks)
*   **`!Boss`**: `00`

## Main Structure (`Sprite_EonOwl_Long`)
This routine serves as a dispatcher for the Eon Owl and Kaepora Gaebora, and includes logic for conditional despawning based on game state.

*   **Kaepora Gaebora Logic**: If the `AreaIndex` is `$0E` (Hall of Secrets map) and certain conditions regarding collected crystals (`$7EF37A`) and the player's possession of the "Song of Soaring" (`$7EF34C`) are met, the sprite is identified as Kaepora Gaebora (`SprSubtype, X` set to `01`) and `Sprite_KaeporaGaebora_Draw` is called.
*   **Eon Owl Logic**: Otherwise, `Sprite_EonOwl_Draw` is called.
*   **Despawning**: If conditions for either character are not met, the sprite despawns (`STZ.w SprState, X`).

```asm
Sprite_EonOwl_Long:
{
  PHB : PHK : PLB
  ; If it is not the Hall of Secrets map
  LDA.b $8A : CMP.b #$0E : BNE .NotGaebora
    ; If the map doesn't have the 6 crystals
     LDA.l $7EF37A : CMP.b #$77 : BNE .Despawn
        ; If the player has the Song of Soaring, despawn
        LDA.l $7EF34C : CMP.b #$03 : BCS .Despawn
          LDA.b #$01 : STA.w SprSubtype, X
          JSR Sprite_KaeporaGaebora_Draw
          JMP .HandleSprite
  .NotGaebora
  JSR Sprite_EonOwl_Draw
  .HandleSprite
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_EonOwl_Main
  .SpriteIsNotActive
  PLB
  RTL
  .Despawn
  STZ.w SprState, X
  PLB
  RTL
}
```

## Initialization (`Sprite_EonOwl_Prep`)
This routine initializes the sprite upon spawning, including setting its hitbox and handling conditional despawning for the intro sequence.

*   **Hitbox**: `SprHitbox, X` is set to `0`.
*   **Kaepora Gaebora Initialization**: If `AreaIndex` is `$0E`, `SprTimerA, X` is set to `$20` and `SprAction, X` to `$03`.
*   **Intro Despawn**: If `AreaIndex` is `$50` (Intro Map) and Link already has the Sword, the sprite despawns.

```asm
Sprite_EonOwl_Prep:
{
  PHB : PHK : PLB

  STZ.w SprHitbox, X

  LDA.b $8A : CMP.b #$0E : BNE .NotGaebora
    LDA.b #$20 : STA.w SprTimerA, X
    LDA.b #$03 : STA.w SprAction, X
  .NotGaebora
  LDA.w AreaIndex : CMP.b #$50 : BNE .not_intro
    ; If Map 0x50, don't spawn after getting sword
    LDA.l Sword : CMP.b #$01 : BCC .continue
       STZ.w SprState, X
    .continue
  .not_intro
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_EonOwl_Main`)
This routine manages the various states and behaviors of both the Eon Owl and Kaepora Gaebora.

*   **`EonOwl_Idle`**: The Eon Owl plays an idle animation and transitions to `EonOwl_IntroDialogue` when Link is nearby.
*   **`EonOwl_IntroDialogue`**: Displays an introductory message and then transitions to `EonOwl_FlyingAway`.
*   **`EonOwl_FlyingAway`**: The Eon Owl plays a flying animation, moves upwards, and despawns after a timer.
*   **`KaeporaGaebora`**: Kaepora Gaebora plays an idle animation and, if Link is at a certain distance and a timer allows, displays a message and transitions to `KaeporaGaebora_Respond`.
*   **`KaeporaGaebora_Respond`**: Processes the player's dialogue choice. If the player declines, it transitions back to `KaeporaGaebora`. If the player accepts, it transitions to `KaeporaGaebora_FlyAway` and grants the "Song of Soaring" (`$7EF34C`).
*   **`KaeporaGaebora_FlyAway`**: Kaepora Gaebora flies upwards and despawns after a timer.

```asm
Sprite_EonOwl_Main:
{
  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw EonOwl_Idle
  dw EonOwl_IntroDialogue
  dw EonOwl_FlyingAway

  dw KaeporaGaebora
  dw KaeporaGaebora_Respond
  dw KaeporaGaebora_FlyAway

  EonOwl_Idle:
  {
    %PlayAnimation(0,1,16)
    JSL GetDistance8bit_Long : CMP #$28 : BCS .not_too_close
      %GotoAction(1)
    .not_too_close
    RTS
  }

  EonOwl_IntroDialogue:
  {
    %PlayAnimation(0,1,16)
    %ShowUnconditionalMessage($00E6)
    LDA.b #$C0 : STA.w SprTimerA, X
    %GotoAction(2)
    RTS
  }

  EonOwl_FlyingAway:
  {
    %PlayAnimation(2,3,10)
    LDA.b #$F8 : STA.w SprYSpeed, X
    JSL   Sprite_Move

    LDA.w SprTimerA, X : CMP.b #$80 : BNE +
      LDA.b #$40 : STA.w SprXSpeed, X
    +

    LDA.w SprTimerA, X : BNE .not_done
      STZ.w SprState, X
    .not_done

    RTS
  }

  ; 0x03 - Kaepora Gaebora
  KaeporaGaebora:
  {
    %PlayAnimation(0,0,1)
    JSL GetDistance8bit_Long : CMP.b #$50 : BCC .not_ready
      LDA.w SprTimerA, X : BNE .not_ready
        %ShowUnconditionalMessage($146)
        %GotoAction(4)
    .not_ready
    RTS
  }

  KaeporaGaebora_Respond:
  {
    LDA $1CE8 : BNE .player_said_no
      %GotoAction(3)
      RTS
    .player_said_no
    %GotoAction(5)
    LDA.b #$60 : STA.w SprTimerA, X
    LDA.b #$03 : STA.l $7EF34C
    RTS
  }

  FlyAwaySpeed = 10
  KaeporaGaebora_FlyAway:
  {
    LDA.b #-FlyAwaySpeed : STA.w SprYSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerA, X : BNE .not_ready
      STZ.w SprState, X
    .not_ready
    RTS
  }
}
```

## Drawing (`Sprite_EonOwl_Draw` and `Sprite_KaeporaGaebora_Draw`)
Both drawing routines handle OAM allocation and animation, using `REP #$20` and `SEP #$20` for 16-bit coordinate calculations. Each has its own specific OAM data for rendering the respective character.

## Design Patterns
*   **Multi-Character NPC**: A single sprite definition dynamically represents two distinct NPCs (Eon Owl and Kaepora Gaebora) based on `AreaIndex` and game state, showcasing efficient sprite reuse.
*   **Conditional Spawning/Despawning**: The sprite's visibility and existence are tightly controlled by game progression, including collected items (crystals, sword) and player inventory (Song of Soaring), making it appear only when relevant to the narrative.
*   **Quest Progression Integration**: The sprite's dialogue and actions are directly linked to specific quest milestones, guiding the player through the game's story.
*   **NPC Interaction with Dialogue Choices**: Kaepora Gaebora presents the player with dialogue options, and the player's choice influences game outcomes, such as receiving the "Song of Soaring."
*   **Flying Behavior**: Implements realistic flying animations and movement, including flying away sequences with controlled speed and timers.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering and positioning.
