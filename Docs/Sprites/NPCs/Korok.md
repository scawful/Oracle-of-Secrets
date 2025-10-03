# Korok

## Overview
The Korok sprite (`!SPRID = Sprite_Korok`) implements a multi-variant NPC system, allowing for different Korok characters (Makar, Hollo, Rown) to appear from a single sprite definition. These Koroks exhibit random walking behavior, engage in dialogue, and are liftable, contributing to environmental interactions and minor puzzles.

## Sprite Properties
*   **`!SPRID`**: `Sprite_Korok` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `08`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `01` (Impervious to all attacks)
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `01`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `03`
*   **`!Persist`**: `01` (Continues to live off-screen)
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
*   **`!DeflectProjectiles`**: `00`
*   **`!ImperviousArrow`**: `00`
*   **`!ImpervSwordHammer`**: `00`
*   **`!Boss`**: `00`

## Main Structure (`Sprite_Korok_Long`)
This routine acts as a dispatcher for drawing the correct Korok variant based on its `SprSubtype, X`. It also handles shadow drawing and dispatches to the main logic if the sprite is active.

```asm
Sprite_Korok_Long:
{
  PHB : PHK : PLB
  LDA $0AA5 : BEQ .done
    LDA.w SprSubtype, X : BEQ .draw_makar
                          CMP.b #$01 : BEQ .draw_hollo
                          CMP.b #$02 : BEQ .draw_rown
    .draw_makar
      JSR Sprite_Korok_DrawMakar
      BRA .done
    .draw_hollo
      JSR Sprite_Korok_DrawHollo
      BRA .done
    .draw_rown
      JSR Sprite_Korok_DrawRown
      BRA .done
  .done

  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Korok_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_Korok_Prep`)
This routine initializes the Korok upon spawning by randomly assigning a `SprSubtype, X` (0-3). This subtype determines which Korok variant (Makar, Hollo, or Rown) the sprite will represent.

```asm
Sprite_Korok_Prep:
{
  PHB : PHK : PLB
  JSL GetRandomInt : AND.b #$03 : STA.w SprSubtype, X
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_Korok_Main`)
The Korok's core behavior is managed by a state machine that includes idle, walking, and liftable states.

*   **`Sprite_Korok_Idle`**: The Korok plays an idle animation. Upon player interaction (`%ShowSolicitedMessage($001D)`), it randomly transitions to a walking state. It also prevents player passage (`Sprite_PlayerCantPassThrough`).
*   **`Sprite_Korok_WalkingDown` / `Up` / `Left` / `Right`**: These states control the Korok's movement in different directions. Each state plays a specific walking animation, sets the appropriate speed (`KorokWalkSpeed`), moves the sprite (`Sprite_Move`), and after a timer (`SprTimerB, X`), randomly transitions to another walking state.
*   **`Sprite_Korok_Liftable`**: This state handles the Korok's interaction when lifted (`Sprite_CheckIfLifted`) and thrown (`ThrownSprite_TileAndSpriteInteraction_long`).

```asm
Sprite_Korok_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Sprite_Korok_Idle
  dw Sprite_Korok_WalkingDown
  dw Sprite_Korok_WalkingUp
  dw Sprite_Korok_WalkingLeft
  dw Sprite_Korok_WalkingRight
  dw Sprite_Korok_Liftable

  Sprite_Korok_Idle:
  {
    %PlayAnimation(0, 0, 10)

    LDA $0AA5 : BNE +
      PHX
      JSL ApplyKorokSpriteSheets
      PLX
      LDA.b #$01 : STA.w $0AA5
    +

    %ShowSolicitedMessage($001D) : BCC .no_talk
      JSL GetRandomInt : AND.b #$03
      STA.w SprAction, X
      RTS
    .no_talk
    JSL Sprite_PlayerCantPassThrough
    RTS
  }

  Sprite_Korok_WalkingDown:
  {
    %PlayAnimation(0, 2, 10)
    LDA.b #KorokWalkSpeed : STA.w SprYSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE +
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_WalkingUp:
  {
    %PlayAnimation(3, 5, 10)
    LDA.b #-KorokWalkSpeed : STA.w SprYSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE +
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_WalkingLeft:
  {
    %PlayAnimation(6, 8, 10)
    LDA.b #KorokWalkSpeed : STA.w SprXSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE +
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_WalkingRight:
  {
    %PlayAnimation(9, 11, 10)
    LDA.b #-KorokWalkSpeed : STA.w SprXSpeed, X
    JSL Sprite_Move

    LDA.w SprTimerB, X : BNE +
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_Liftable:
  {
    JSL Sprite_Move
    JSL Sprite_CheckIfLifted
    JSL ThrownSprite_TileAndSpriteInteraction_long
    RTS
  }

}
```

## Drawing (`Sprite_Korok_DrawMakar`, `Sprite_Korok_DrawHollo`, `Sprite_Korok_DrawRown`)
Each Korok variant has its own dedicated drawing routine (`Sprite_Korok_DrawMakar`, `Sprite_Korok_DrawHollo`, `Sprite_Korok_DrawRown`). These routines handle OAM allocation and animation, and explicitly use `REP #$20` and `SEP #$20` for 16-bit coordinate calculations. Each routine contains its own specific OAM data for rendering the respective Korok character.

## Design Patterns
*   **Multi-Variant NPC**: A single sprite definition (`Sprite_Korok`) is used to represent multiple distinct Korok characters (Makar, Hollo, Rown) based on a randomly assigned `SprSubtype`, showcasing efficient resource utilization and varied visual appearances.
*   **Randomized Behavior**: The Korok's initial variant and its walking directions are randomized, adding an element of unpredictability and variety to encounters.
*   **NPC Interaction**: The Korok can be interacted with through dialogue (`%ShowSolicitedMessage`) and is liftable (`Sprite_CheckIfLifted`), allowing for environmental puzzles or simple interactions.
*   **Conditional Drawing**: The drawing routine dispatches to different sub-routines based on the Korok's subtype, allowing for distinct visual appearances for each variant.
*   **Player Collision**: Implements `Sprite_PlayerCantPassThrough` to make the NPC a solid object that Link cannot walk through.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
